import struct
from datetime import UTC, datetime
from typing import NamedTuple

from commons.contracts.v1.api.telemetry import TelemetryPointDto


class NplHeader(NamedTuple):
    signature: int
    data_size: int
    flags: int
    crc: int
    type: int
    peer_address: int
    request_id: int


class NphHeader(NamedTuple):
    service_id: int
    type: int
    flags: int
    request_id: int


class NdtpParser:
    NPL_FMT = "<HHHHIBH"
    NPL_SIZE = 15

    NPH_FMT = "<HHHI"
    NPH_SIZE = 10

    @staticmethod
    def parse_npl(data: bytes) -> NplHeader:
        if len(data) < NdtpParser.NPL_SIZE:
            raise ValueError("Insufficient data for NPL")

        signature, data_size, flags, crc, p_type, peer_address, request_id = (
            struct.unpack(NdtpParser.NPL_FMT, data[: NdtpParser.NPL_SIZE])
        )
        return NplHeader(
            signature=signature,
            data_size=data_size,
            flags=flags,
            crc=crc,
            type=p_type,
            peer_address=peer_address,
            request_id=request_id,
        )

    @staticmethod
    def parse_nph(data: bytes) -> NphHeader:
        if len(data) < NdtpParser.NPH_SIZE:
            raise ValueError("Insufficient data for NPH")

        service_id, p_type, flags, request_id = struct.unpack(
            NdtpParser.NPH_FMT, data[: NdtpParser.NPH_SIZE]
        )
        return NphHeader(
            service_id=service_id,
            type=p_type,
            flags=flags,
            request_id=request_id,
        )

    @staticmethod
    def parse_realtime_cells(data: bytes) -> TelemetryPointDto | None:
        offset = 0
        total_len = len(data)

        while offset < total_len:
            if offset + 2 > total_len:
                break

            cell_type = data[offset]
            offset += 2

            if cell_type == 0:
                if offset + 26 > total_len:
                    break

                cell_data = data[offset : offset + 26]

                timestamp, lon_raw, lat_raw, dop_bits_byte = struct.unpack(
                    "<IIIB", cell_data[:13]
                )
                speed_avg = struct.unpack("<H", cell_data[14:16])[0]
                course = struct.unpack("<H", cell_data[18:20])[0]

                lon = lon_raw / 10000000.0
                lat = lat_raw / 10000000.0

                is_north = (dop_bits_byte & 0x20) != 0
                is_east = (dop_bits_byte & 0x40) != 0

                if not is_north:
                    lat = -lat
                if not is_east:
                    lon = -lon

                return TelemetryPointDto(
                    timestamp=datetime.fromtimestamp(timestamp, UTC),
                    longitude=lon,
                    latitude=lat,
                    speed=speed_avg,
                    course=course,
                )
            elif cell_type == 2:
                offset += 26
            elif cell_type == 8:
                offset += 6
            elif cell_type == 10:
                offset += 37
            elif cell_type == 16:
                offset += 8
            elif cell_type == 15:
                offset += 50
            else:
                break

        return None
