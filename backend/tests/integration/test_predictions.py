from datetime import UTC, datetime, timedelta

import pytest
import respx
from httpx import Response

from backend.modules.schedule.models import SchedulePlan
from backend.modules.telemetry.models import RedisTelemetryRecord
from backend.modules.telemetry.repository import TelemetryRedisRepository
from backend.settings import Settings
from commons.contracts.v1.ml.responses import MLPredictionResponse
from commons.enums import IncidentPattern, RiskLevel


@pytest.mark.asyncio
async def test_dashboard_triggers_prediction(app_client, redis_client, session):
    settings = Settings()

    tr_id = 777
    current_time = datetime.now(UTC)

    repository = TelemetryRedisRepository(redis_client, settings)
    point = RedisTelemetryRecord(
        timestamp=current_time, longitude=37.0, latitude=55.0, speed=25, course=90
    )
    await repository.add_point(tr_id, point)

    plan = SchedulePlan(
        tr_id=tr_id,
        stop_id=1010,
        time_begin=current_time + timedelta(minutes=10),
        address="Test Stop",
        longitude=37.1,
        latitude=55.1,
    )
    session.add(plan)
    await session.commit()

    mock_response = MLPredictionResponse(
        predicted_delay_s=120.0,
        risk_level=RiskLevel.YELLOW,
        pattern_reason=IncidentPattern.TRAFFIC_JAM,
    )

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post(settings.ml.url).mock(
            return_value=Response(200, json=mock_response.model_dump(mode="json"))
        )

        await app_client.post(f"/api/v1/predictions/{tr_id}/trigger")
        response = await app_client.get("/api/v1/dashboard/state")

        assert response.status_code == 200
        data = response.json()

        assert "vehicles" in data
        assert len(data["vehicles"]) == 1

        v = data["vehicles"][0]
        assert v["tr_id"] == tr_id
        assert v["risk_color"] == "YELLOW"
        assert v["incident_card"]["predicted_delay_s"] == 120.0

        assert route.called
