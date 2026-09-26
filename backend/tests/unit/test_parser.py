import struct
from datetime import UTC, datetime

import pytest

from backend.tcp.parser import NdtpParser
from commons.contracts.v1.api.telemetry import TelemetryPointDto


def test_parse_npl_success():
    data = struct.pack("<HHHHIBH", 0x7E7E, 50, 0, 0, 1, 123, 1001)

    npl = NdtpParser.parse_npl(data)

    assert npl.signature == 0x7E7E
    assert npl.data_size == 50
    assert npl.peer_address == 123
    assert npl.request_id == 1001


def test_parse_npl_insufficient_data():
    with pytest.raises(ValueError, match="Insufficient data for NPL"):
        NdtpParser.parse_npl(b"\x7e\x7e")


def test_parse_nph_success():
    data = struct.pack("<HHHI", 10, 101, 0, 2002)

    nph = NdtpParser.parse_nph(data)

    assert nph.service_id == 10
    assert nph.type == 101
    assert nph.request_id == 2002


def test_parse_nph_insufficient_data():
    with pytest.raises(ValueError, match="Insufficient data for NPH"):
        NdtpParser.parse_nph(b"\x00\x00")


def test_parse_realtime_cells_success():
    cell_type_data = struct.pack("BB", 0, 0)

    ts = int(datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC).timestamp())
    lon_raw = int(37.6173 * 10000000)
    lat_raw = int(55.7558 * 10000000)
    dop = 0x20 | 0x40

    data_block = bytearray(26)
    struct.pack_into("<IIIB", data_block, 0, ts, lon_raw, lat_raw, dop)
    struct.pack_into("<H", data_block, 14, 45)
    struct.pack_into("<H", data_block, 18, 180)

    full_data = cell_type_data + bytes(data_block)

    point = NdtpParser.parse_realtime_cells(full_data)

    assert point is not None
    assert isinstance(point, TelemetryPointDto)
    assert point.longitude == pytest.approx(37.6173)
    assert point.latitude == pytest.approx(55.7558)
    assert point.speed == 45
    assert point.course == 180
    assert point.timestamp.year == 2026


def test_parse_realtime_cells_south_west():
    cell_type_data = struct.pack("BB", 0, 0)

    ts = int(datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC).timestamp())
    lon_raw = int(37.6173 * 10000000)
    lat_raw = int(55.7558 * 10000000)
    dop = 0x00

    data_block = bytearray(26)
    struct.pack_into("<IIIB", data_block, 0, ts, lon_raw, lat_raw, dop)

    full_data = cell_type_data + bytes(data_block)

    point = NdtpParser.parse_realtime_cells(full_data)

    assert point is not None
    assert point.longitude == pytest.approx(-37.6173)
    assert point.latitude == pytest.approx(-55.7558)


def test_parse_realtime_cells_empty():
    point = NdtpParser.parse_realtime_cells(b"")
    assert point is None


def test_parse_realtime_cells_unknown_cell():
    point = NdtpParser.parse_realtime_cells(b"\xff\x00\x00\x00")
    assert point is None
