import argparse
import json
import platform
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from ml.bootstrap import create_app
from ml.models.predictor import Predictor
from ml.settings import get_settings

from commons.contracts.v1.ml.requests import MLPredictionRequest


def payload(count=60):
    now = datetime(2026, 1, 6, 12, tzinfo=UTC)
    return {
        "tr_id": 122048,
        "target_stop_id": 1,
        "current_time_T": now.isoformat(),
        "target_time_begin": (now + timedelta(seconds=720)).isoformat(),
        "cur_dev_s": 20,
        "segment_avg_speed": 20,
        "idle_time_s": 0,
        "coverage_ratio": 1,
        "window_start_time": (now - timedelta(seconds=900)).isoformat(),
        "window_end_time": now.isoformat(),
        "recent_telemetry": [
            {
                "timestamp": (
                    now - timedelta(seconds=900 * i / max(1, count))
                ).isoformat(),
                "packet_time": now.isoformat(),
                "longitude": 37 + 0.00001 * i,
                "latitude": 55,
                "speed": 20,
                "course": 90,
                "location_valid": True,
                "is_historical": False,
            }
            for i in range(count)
        ],
    }


def quantiles(values):
    return dict(
        zip(
            ["p50_ms", "p95_ms", "p99_ms"],
            np.quantile(values, [0.5, 0.95, 0.99]).tolist(),
        )
    )


def measure(directory, count=60, repeats=300):
    predictor = Predictor(directory)
    data = payload(count)
    request = MLPredictionRequest.model_validate(data)
    settings = get_settings()
    original_directory = settings.app.model_dir
    settings.app.model_dir = str(Path(directory).resolve())
    app = create_app()
    try:
        return _measure_app(app, predictor, request, data, count, repeats)
    finally:
        settings.app.model_dir = original_directory


def _measure_app(app, predictor, request, data, count, repeats):
    with TestClient(app) as client:
        app.state.predictor = predictor
        for _ in range(30):
            predictor.predict(request)
            client.post("/predict", json=data).raise_for_status()
        direct, api = [], []
        for _ in range(repeats):
            start = time.perf_counter()
            predictor.predict(request)
            direct.append((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            client.post("/predict", json=data).raise_for_status()
            api.append((time.perf_counter() - start) * 1000)
    return {
        "points": count,
        "direct": quantiles(direct),
        "api": quantiles(api),
        "scope": "TestClient in-process including JSON validation and routing, serial; no network",
        "hardware": platform.platform(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = [measure(args.model, count) for count in (0, 60, 180)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
