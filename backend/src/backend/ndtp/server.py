import asyncio
import logging
from datetime import UTC, datetime

from backend.modules.reference.repository import DeviceRepository
from backend.modules.reference.service import DeviceService
from backend.modules.telemetry.repository import TelemetryRedisRepository
from backend.modules.telemetry.service import TelemetryService
from backend.ndtp.parser import NdtpParser
from backend.settings import Settings

logger = logging.getLogger("uvicorn.ndtp")


class NdtpServer:
    def __init__(
        self,
        host: str,
        port: int,
        session_maker,
        redis_client,
        settings: Settings,
    ):
        self.host = host
        self.port = port
        self.session_maker = session_maker
        self.redis_client = redis_client
        self.settings = settings
        self.server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port,
        )
        logger.info(f"NDTP TCP server listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("NDTP TCP server stopped")

    async def handle_client(self, reader, writer) -> None:
        addr = writer.get_extra_info("peername")
        logger.info(f"New connection from {addr}")

        try:
            while True:
                npl_data = await reader.readexactly(NdtpParser.NPL_SIZE)
                npl = NdtpParser.parse_npl(npl_data)

                if npl.signature != 0x7E7E:
                    logger.warning(f"Invalid signature from {addr}: {npl.signature}")
                    break

                body_size = npl.data_size
                if body_size < NdtpParser.NPH_SIZE:
                    logger.warning(f"Invalid body size from {addr}: {body_size}")
                    break

                body_data = await reader.readexactly(body_size)
                nph = NdtpParser.parse_nph(body_data[: NdtpParser.NPH_SIZE])

                if nph.type == 100:
                    logger.info(f"Handshake from unit {npl.peer_address}")
                    continue
                elif nph.type == 101:
                    cells_data = body_data[NdtpParser.NPH_SIZE :]
                    packet_time = datetime.now(UTC)
                    point = NdtpParser.parse_realtime_cells(
                        cells_data, packet_time=packet_time, is_historical=False
                    )

                    if point:
                        try:
                            cache_key = f"device_mapping:{npl.peer_address}"
                            tr_id_str = await self.redis_client.get(cache_key)

                            if tr_id_str:
                                tr_id = int(tr_id_str)
                            else:
                                async with (
                                    self.session_maker() as session,
                                    session.begin(),
                                ):
                                    device_service = DeviceService(
                                        DeviceRepository(session)
                                    )
                                    tr_id = await device_service.get_tr_id(
                                        npl.peer_address
                                    )

                                if tr_id:
                                    await self.redis_client.setex(
                                        cache_key, 3600, tr_id
                                    )

                            if not tr_id:
                                logger.warning(f"Unknown unit_id {npl.peer_address}")
                                continue

                            telemetry_service = TelemetryService(
                                TelemetryRedisRepository(
                                    self.redis_client, self.settings
                                )
                            )

                            if (
                                (packet_time - point.timestamp).total_seconds()
                                > self.settings.app.historical_packet_delay_s
                            ):
                                point = point.model_copy(update={"is_historical": True})

                            await telemetry_service.add_point(tr_id, point)
                            logger.info(f"Saved telemetry for tr_id={tr_id}: {point}")
                        except Exception as e:
                            logger.error(f"Error processing telemetry from {addr}: {e}")
                else:
                    logger.debug(f"Unknown NPH type {nph.type} from {addr}")

        except asyncio.IncompleteReadError:
            logger.debug(f"Connection closed by {addr}")
        except ConnectionResetError:
            logger.debug(f"Connection reset by {addr}")
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
