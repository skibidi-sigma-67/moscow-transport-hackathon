from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from ml.main import app

from commons.contracts.v1.ml.responses import MLPredictionResponse


def payload():
    now = datetime(2026, 1, 6, 12, tzinfo=UTC)
    return {
        "tr_id": 1,
        "target_stop_id": 1,
        "current_time_T": now.isoformat(),
        "target_time_begin": (now + timedelta(seconds=720)).isoformat(),
        "cur_dev_s": -40,
        "segment_avg_speed": 20,
        "idle_time_s": 0,
        "coverage_ratio": 0.1,
        "window_start_time": (now - timedelta(seconds=900)).isoformat(),
        "window_end_time": now.isoformat(),
        "recent_telemetry": [
            {
                "timestamp": now.isoformat(),
                "packet_time": now.isoformat(),
                "longitude": 37,
                "latitude": 55,
                "speed": 20,
                "course": 90,
                "location_valid": True,
                "is_historical": False,
            }
        ],
    }


def test_api_contract_and_validation():
    with TestClient(app) as client:
        data = payload()
        result = client.post("/predict", json=data)
        assert result.status_code == 200
        response = MLPredictionResponse.model_validate(result.json())
        assert set(result.json()) == {
            "predicted_delay_s",
            "risk_level",
            "pattern_reason",
        }
        assert response.pattern_reason is None
        assert client.get("/health").status_code == 200
        data["target_time_begin"] = data["current_time_T"]
        assert client.post("/predict", json=data).status_code == 422
        data = payload()
        del data["coverage_ratio"]
        assert client.post("/predict", json=data).status_code == 422
