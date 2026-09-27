import json
from datetime import UTC, datetime, timedelta

import pytest
from catboost import CatBoostRegressor, Pool
from fastapi.testclient import TestClient
from ml.main import app
from ml.settings import get_settings

from commons.contracts.v1.ml.responses import MLPredictionResponse
from commons.enums import PredictionStatus


@pytest.fixture(scope="module")
def model_dir(tmp_path_factory):
    directory = tmp_path_factory.mktemp("model")
    model = CatBoostRegressor(
        iterations=2,
        depth=2,
        thread_count=1,
        verbose=False,
        allow_writing_files=False,
    )
    model.fit(
        Pool(
            [[-40.0], [0.0], [40.0]],
            [-30.0, 0.0, 30.0],
            feature_names=["cur_dev_s"],
        )
    )
    model.save_model(str(directory / "delay.cbm"))
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "feature_version": 5,
                "features": ["cur_dev_s"],
                "mode": "direct",
                "model_version": "test-model",
            }
        )
    )
    return directory


@pytest.fixture
def client(model_dir, monkeypatch):
    monkeypatch.setenv("APP__MODEL_DIR", str(model_dir))
    monkeypatch.setenv("APP__STRATEGY", "baseline")
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


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


def test_api_contract_and_validation(client):
    data = payload()
    result = client.post("/predict", json=data)
    assert result.status_code == 200
    response = MLPredictionResponse.model_validate(result.json())
    assert set(result.json()) == {
        "predicted_delay_s",
        "risk_level",
        "pattern_reason",
        "status",
    }
    assert response.pattern_reason is None
    assert response.status == PredictionStatus.OK
    assert client.get("/health").status_code == 200
    data["target_time_begin"] = data["current_time_T"]
    assert client.post("/predict", json=data).status_code == 422
    data = payload()
    del data["coverage_ratio"]
    assert client.post("/predict", json=data).status_code == 422


def test_prediction_survives_missing_history_and_reconnect(client):
    data = payload()
    data["recent_telemetry"][0]["is_historical"] = True
    result = client.post("/predict", json=data)
    assert result.status_code == 200
    assert result.json()["status"] == PredictionStatus.DEGRADED
    data["recent_telemetry"] = []
    result = client.post("/predict", json=data)
    assert result.status_code == 200
    assert result.json()["status"] == PredictionStatus.DEGRADED
    data = payload()
    data["recent_telemetry"][0]["timestamp"] = (
        datetime.fromisoformat(data["current_time_T"]) - timedelta(seconds=60)
    ).isoformat()
    result = client.post("/predict", json=data)
    assert result.status_code == 200
    assert result.json()["status"] == PredictionStatus.DEGRADED
    data = payload()
    result = client.post("/predict", json=data)
    assert result.status_code == 200
    assert result.json()["status"] == PredictionStatus.OK
