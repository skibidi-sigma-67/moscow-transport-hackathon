import asyncio
import logging

from backend.modules.reference.repository import DeviceRepository
from backend.modules.reference.service import DeviceService
from backend.modules.telemetry.repository import TelemetryRedisRepository
from backend.modules.telemetry.service import TelemetryService
from backend.settings import Settings
from backend.tcp.parser import NdtpParser

logger = logging.getLogger(__name__)


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
        addrs = ", ".join(str(sock.getsockname()) for sock in self.server.sockets)
        logger.info(f"NDTP TCP server listening on {addrs}")

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("NDTP TCP server stopped")

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        addr = writer.get_extra_info("peername")
        logger.debug(f"New connection from {addr}")

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
                    logger.debug(f"Handshake from unit {npl.peer_address}")
                    continue
                elif nph.type == 101:
                    cells_data = body_data[NdtpParser.NPH_SIZE :]
                    point = NdtpParser.parse_realtime_cells(cells_data)

                    if point:
                        try:
                            async with self.session_maker() as session:
                                device_service = DeviceService(
                                    DeviceRepository(session)
                                )
                                telemetry_service = TelemetryService(
                                    TelemetryRedisRepository(
                                        self.redis_client, self.settings
                                    )
                                )

                                mapping = await device_service.register_device(
                                    unit_id=npl.peer_address, tr_id=npl.peer_address
                                )

                                await telemetry_service.add_point(mapping.tr_id, point)
                                logger.debug(
                                    f"Saved telemetry for tr_id={mapping.tr_id}"
                                )
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
