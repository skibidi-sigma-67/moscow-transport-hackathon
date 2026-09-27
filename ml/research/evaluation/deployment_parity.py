import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from ml.models.predictor import Predictor

from commons.contracts.v1.ml.requests import MLPredictionRequest, TelemetryPoint
from research.data.dataset import OUTPUT, ROOT
from research.legacy_dataset import load, seconds


def requests(root):
    root = Path(root)
    points, _, _, _ = load(root, "validate")
    traffic = pd.read_csv(
        root / "validate/traffic.csv",
        usecols=[
            "tr_id",
            "event_time",
            "lon",
            "lat",
            "speed",
            "heading",
            "location_valid",
        ],
    )
    traffic["time"] = seconds(traffic.event_time)
    histories = {int(k): g.sort_values("time") for k, g in traffic.groupby("tr_id")}
    for row in points.itertuples():
        now = datetime.fromtimestamp(row.now, UTC)
        vehicle = histories.get(int(row.tr_id))
        telemetry = []
        if vehicle is not None:
            times = vehicle.time.to_numpy()
            window = vehicle.iloc[
                np.searchsorted(times, row.now - 900) : np.searchsorted(
                    times, row.now, side="right"
                )
            ]
            telemetry = [
                TelemetryPoint(
                    timestamp=datetime.fromtimestamp(point.time, UTC),
                    packet_time=datetime.fromtimestamp(point.time, UTC),
                    longitude=point.lon,
                    latitude=point.lat,
                    speed=point.speed,
                    course=point.heading,
                    location_valid=bool(point.location_valid),
                    is_historical=False,
                )
                for point in window.itertuples()
            ]
        yield (
            row.sample_id,
            MLPredictionRequest(
                tr_id=row.tr_id,
                target_stop_id=row.target_stop_id,
                target_time_begin=datetime.fromtimestamp(row.target_time, UTC),
                current_time_T=now,
                cur_dev_s=row.cur_dev_s,
                aggregates={
                    "segment_avg_speed": 0,
                    "idle_time_s": 0,
                    "coverage_ratio": 0,
                },
                window={
                    "start_time": now - timedelta(seconds=900),
                    "end_time": now,
                    "recent_points": telemetry,
                }
            ),
        )


def run(root, bundle, submission):
    predictor = Predictor(bundle, "schedule_ensemble")
    expected = pd.read_csv(submission, sep=";").set_index("sample_id")
    predictions = {
        sample_id: predictor.predict(request).predicted_delay_s
        for sample_id, request in requests(root)
    }
    if set(predictions) != set(expected.index):
        raise ValueError("Submission and deployment requests differ")
    errors = np.array(
        [
            abs(predictions[sample_id] - expected.loc[sample_id, "prediction"])
            for sample_id in expected.index
        ]
    )
    result = {
        "rows": len(errors),
        "max_absolute_difference_s": float(errors.max()),
        "mean_absolute_difference_s": float(errors.mean()),
    }
    if result["max_absolute_difference_s"] > 1e-6:
        raise ValueError(f"Deployment prediction differs from submission: {result}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument(
        "--submission", type=Path, default=OUTPUT / "model_4/submission.csv"
    )
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.bundle, args.submission)))
