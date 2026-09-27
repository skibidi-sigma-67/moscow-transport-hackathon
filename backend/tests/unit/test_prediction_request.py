import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.modules.predictions.service import PredictionService
from backend.modules.telemetry.models import RedisTelemetryRecord
from backend.settings import Settings
from commons.contracts.v1.ml.responses import MLPredictionResponse
from commons.enums import RiskLevel


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_point", [False, True])
async def test_missing_valid_gps_sends_serializable_request(invalid_point):
    now = datetime(2026, 1, 6, 12, tzinfo=UTC)
    history = (
        [
            RedisTelemetryRecord(
                timestamp=now,
                longitude=0,
                latitude=0,
                speed=0,
                course=0,
                location_valid=False,
            )
        ]
        if invalid_point
        else []
    )
    telemetry = SimpleNamespace(get_history=AsyncMock(return_value=history))
    redis = SimpleNamespace(
        get=AsyncMock(return_value=now.isoformat().encode()), set=AsyncMock()
    )
    schedule = SimpleNamespace(
        get_previous_stop=AsyncMock(return_value=None),
        get_next_stop=AsyncMock(
            return_value=SimpleNamespace(
                stop_id=10,
                time_begin=now + timedelta(minutes=12),
                longitude=37.5,
                latitude=55.7,
            )
        ),
        get_stop_times=AsyncMock(return_value=[]),
    )
    ml = SimpleNamespace(
        get_prediction=AsyncMock(
            return_value=(
                MLPredictionResponse(predicted_delay_s=0, risk_level=RiskLevel.GREEN),
                None,
            )
        )
    )
    repository = SimpleNamespace(
        save_prediction=AsyncMock(
            return_value=SimpleNamespace(
                id=1,
                tr_id=1,
                predicted_delay_s=0,
                risk_level=RiskLevel.GREEN,
                pattern_reason=None,
                created_at=now,
            )
        )
    )
    service = PredictionService(repository, telemetry, redis, schedule, ml, Settings())
    await service.generate_prediction(1)

    request = ml.get_prediction.call_args.args[0]
    assert request.route_features is None
    json.dumps(request.model_dump(mode="json"), allow_nan=False)
