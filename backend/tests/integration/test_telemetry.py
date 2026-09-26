from datetime import UTC, datetime, timedelta

import pytest

from backend.modules.telemetry.models import RedisTelemetryRecord
from backend.modules.telemetry.repository import TelemetryRedisRepository
from backend.settings import Settings


@pytest.mark.asyncio
async def test_telemetry_add_point_and_get_history(redis_client):
    settings = Settings()
    repo = TelemetryRedisRepository(redis_client, settings)

    unit_id = 999

    point1 = RedisTelemetryRecord(
        timestamp=datetime.now(UTC) - timedelta(minutes=1),
        longitude=37.0,
        latitude=55.0,
        speed=10.5,
        course=90.0,
    )

    point2 = RedisTelemetryRecord(
        timestamp=datetime.now(UTC),
        longitude=37.1,
        latitude=55.1,
        speed=15.0,
        course=92.0,
    )

    await repo.add_point(unit_id, point1)
    await repo.add_point(unit_id, point2)

    history = await repo.get_history(unit_id)

    assert len(history) == 2
    assert history[0].longitude == 37.0
    assert history[1].longitude == 37.1


@pytest.mark.asyncio
async def test_telemetry_ltrim_max_history(redis_client):
    settings = Settings()
    settings.app.telemetry_max_history = 3
    repo = TelemetryRedisRepository(redis_client, settings)

    unit_id = 888

    for i in range(5):
        point = RedisTelemetryRecord(
            timestamp=datetime.now(UTC),
            longitude=37.0 + (i * 0.1),
            latitude=55.0,
            speed=10.0,
            course=90.0,
        )
        await repo.add_point(unit_id, point)

    history = await repo.get_history(unit_id)

    assert len(history) == 3
    assert history[0].longitude == pytest.approx(37.2)
    assert history[-1].longitude == pytest.approx(37.4)


@pytest.mark.asyncio
async def test_telemetry_get_active_vehicles(redis_client):
    settings = Settings()
    repo = TelemetryRedisRepository(redis_client, settings)

    await repo.add_point(
        101,
        RedisTelemetryRecord(
            timestamp=datetime.now(UTC),
            longitude=37.0,
            latitude=55.0,
            speed=10,
            course=90,
        ),
    )

    await repo.add_point(
        102,
        RedisTelemetryRecord(
            timestamp=datetime.now(UTC) - timedelta(minutes=15),
            longitude=37.0,
            latitude=55.0,
            speed=10,
            course=90,
        ),
    )

    active = await repo.get_active_vehicles(minutes=5)

    assert 101 in active
    assert 102 not in active
