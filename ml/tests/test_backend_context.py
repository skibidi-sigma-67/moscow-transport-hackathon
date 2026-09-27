from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from ml.main import app

from commons.contracts.v1.api.telemetry import TelemetryPointDto
from commons.contracts.v1.ml.requests import MLPredictionRequest
from commons.ml_context import prepare_context

NOW = datetime(2026, 1, 6, 12, tzinfo=UTC)


def payload():
    return {
        "tr_id": 123,
        "target_stop_id": 2,
        "current_time_T": NOW.isoformat(),
        "target_time_begin": (NOW + timedelta(seconds=720)).isoformat(),
        "cur_dev_source": "gps",
        "cur_dev_s": None,
        "window_start_time": (NOW - timedelta(minutes=30)).isoformat(),
        "window_end_time": NOW.isoformat(),
        "planned_stops": [
            {
                "stop_id": 1,
                "time_begin": (NOW - timedelta(seconds=50)).isoformat(),
                "longitude": 37,
                "latitude": 55,
            },
            {
                "stop_id": 2,
                "time_begin": (NOW + timedelta(seconds=720)).isoformat(),
                "longitude": 37.1,
                "latitude": 55.1,
            },
        ],
        "recent_telemetry": [
            {
                "timestamp": (NOW - timedelta(seconds=s)).isoformat(),
                "packet_time": NOW.isoformat(),
                "longitude": 37,
                "latitude": 55,
                "speed": 0,
                "course": 90,
                "location_valid": True,
                "is_historical": True,
            }
            for s in [20, 10]
        ],
    }


def context(data):
    return prepare_context(MLPredictionRequest.model_validate(data))


def test_api_validates_window_and_target_and_reports_quality():
    with TestClient(app) as client:
        data = payload()
        result = client.post("/predict", json=data)
        assert result.status_code == 200
        assert result.json()["historical_count"] == 2
        assert result.json()["status"] == "DEGRADED"
        assert result.json()["model_version"].endswith("-gps")
        data["window_end_time"] = (NOW + timedelta(seconds=1)).isoformat()
        assert client.post("/predict", json=data).status_code == 422
        data = payload()
        data["planned_stops"].append(
            {"stop_id": 3, "time_begin": (NOW + timedelta(seconds=660)).isoformat()}
        )
        assert client.post("/predict", json=data).status_code == 422


@pytest.mark.asyncio
async def test_real_backend_request_runs_through_ml_api_and_persists_context():
    from backend.modules.predictions.service import PredictionService
    from backend.settings import Settings

    data = payload()
    telemetry = SimpleNamespace(
        get_history=AsyncMock(
            return_value=[
                TelemetryPointDto.model_validate(p) for p in data["recent_telemetry"]
            ]
        )
    )
    plans = [
        SimpleNamespace(
            stop_id=p["stop_id"],
            time_begin=datetime.fromisoformat(p["time_begin"]),
            longitude=p.get("longitude"),
            latitude=p.get("latitude"),
        )
        for p in data["planned_stops"]
    ]
    schedule = SimpleNamespace(
        repository=SimpleNamespace(get_vehicle_plan=AsyncMock(return_value=plans))
    )
    cache = AsyncMock()
    cache.get.side_effect = lambda key: (
        NOW.isoformat().encode() if key == "replay:clock" else None
    )
    repo = SimpleNamespace(save_prediction=AsyncMock())

    def saved(**kwargs):
        return SimpleNamespace(id=1, created_at=NOW, **kwargs)

    repo.save_prediction.side_effect = saved
    with TestClient(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://ml"
        ) as client:
            service = PredictionService(
                repo, telemetry, cache, schedule, Settings(), client
            )
            result = await service.generate_prediction(123)
    detail = result.prediction_context
    assert detail["telemetry_time_policy"] == "event"
    assert detail["telemetry_count"] == 2
    assert detail["historical_count"] == 2
    assert detail["model_version"].endswith("-gps")
    assert repo.save_prediction.call_args.kwargs["status"] == "DEGRADED"
