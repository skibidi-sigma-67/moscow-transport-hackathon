import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from commons.contracts.v1.ml.requests import MLPredictionRequest
from commons.enums import PredictionStatus
from ml.bootstrap import create_app
from ml.models.predictor import Predictor
from ml.settings import get_settings
from test_api import payload

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"


def route_payload():
    data = payload()
    data["route_features"] = {
        "cur_dev_missing": 0.0,
        "horizon_s": 720.0,
        "hour_sin": 0.0,
        "hour_cos": -1.0,
        "stops_ahead": 3.0,
        "target_lon": 37.5,
        "target_lat": 55.9,
        "distance_target_m": 1000.0,
        "gps_age_s": 0.0,
        "last_lon": 37.0,
        "last_lat": 55.0,
        "last_speed": 20.0,
        "heading_alignment": 1.0,
        "target_east_m": 500.0,
        "target_north_m": 700.0,
    }
    return data


def test_ensemble_uses_all_three_models_and_baseline_fallback():
    predictor = Predictor(ARTIFACTS, "schedule_ensemble")
    data = route_payload()
    request = MLPredictionRequest.model_validate(data)
    values = data["route_features"] | {"cur_dev_s": data["cur_dev_s"]}
    expected = sum(
        weight
        * float(
            model.predict(
                np.array([[values[column] for column in columns]], dtype=float),
                thread_count=1,
            )[0]
        )
        for model, columns, weight in predictor.ensemble
    )
    response = predictor.predict(request)
    assert response.predicted_delay_s == pytest.approx(expected)
    assert response.status == PredictionStatus.OK

    data.pop("route_features")
    fallback = predictor.predict(MLPredictionRequest.model_validate(data))
    baseline = Predictor(ARTIFACTS, "baseline").predict(
        MLPredictionRequest.model_validate(data)
    )
    assert fallback.predicted_delay_s == pytest.approx(baseline.predicted_delay_s)
    assert fallback.status == PredictionStatus.DEGRADED


def test_schedule_plan_supplies_missing_route_features():
    predictor = Predictor(ARTIFACTS, "schedule_ensemble")
    data = payload()
    target = datetime(2026, 1, 6, 6, 41, tzinfo=UTC)
    now = target - timedelta(seconds=720)
    data.update(
        tr_id=122658,
        target_stop_id=53699433974,
        current_time_T=now.isoformat(),
        target_time_begin=target.isoformat(),
    )
    data["window"]["start_time"] = (now - timedelta(seconds=900)).isoformat()
    data["window"]["end_time"] = now.isoformat()
    data["window"]["recent_points"][0]["timestamp"] = now.isoformat()
    data["window"]["recent_points"][0]["packet_time"] = now.isoformat()
    data["window"]["recent_points"].append(
        {**data["window"]["recent_points"][0], "speed": 12.0}
    )
    request = MLPredictionRequest.model_validate(data)
    route = predictor.schedule_plan.route_features(request)
    assert route is not None
    assert route.stops_ahead >= 1
    assert route.last_speed == 12.0
    auto = predictor.predict(request)
    explicit = predictor.predict(request.model_copy(update={"route_features": route}))
    assert auto.predicted_delay_s == pytest.approx(explicit.predicted_delay_s)
    assert auto.status == PredictionStatus.OK

    data["window"]["recent_points"] = []
    sparse = predictor.predict(MLPredictionRequest.model_validate(data))
    assert np.isfinite(sparse.predicted_delay_s)
    assert sparse.status == PredictionStatus.DEGRADED


def test_ensemble_api_and_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("APP__MODEL_DIR", str(ARTIFACTS))
    monkeypatch.setenv("APP__STRATEGY", "schedule_ensemble")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            assert client.get("/health").json()["model"] == "legacy-score-anchored-v5"
            result = client.post("/predict", json=route_payload())
            assert result.status_code == 200
            assert result.json()["status"] == PredictionStatus.OK
    finally:
        get_settings.cache_clear()

    bundle = tmp_path / "bundle"
    shutil.copytree(ARTIFACTS, bundle)
    metadata = bundle / "model_2" / "metadata.json"
    metadata.write_text(metadata.read_text() + "\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        Predictor(bundle, "schedule_ensemble")
