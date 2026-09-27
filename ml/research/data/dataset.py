import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from ml.features import FEATURE_VERSION, features, history, timestamp

from commons.contracts.v1.ml.requests import MLPredictionRequest, TelemetryPoint

ROOT = Path(__file__).resolve().parents[3] / "dataset"
OUTPUT = Path(__file__).resolve().parents[2] / "artifacts"


def seconds(values):
    return (
        pd.to_datetime(values, format="mixed", utc=True)
        .dt.as_unit("ns")
        .astype("int64")
        / 1e9
    )


def load(root, split, policy="event", include_sequence=True):
    if policy not in ("event", "receive"):
        raise ValueError("Unknown availability policy")
    root = Path(root)
    points = pd.read_csv(
        root
        / (
            f"labels/labels_{split}.csv"
            if split != "validate"
            else "validate/points.csv"
        )
    )
    points["now"] = seconds(points["T"])
    points["target_time"] = seconds(points.target_time_begin)
    traffic = pd.read_csv(
        root / split / "traffic.csv",
        usecols=[
            "tr_id",
            "event_time",
            "receive_time",
            "lon",
            "lat",
            "speed",
            "heading",
            "location_valid",
        ],
    )
    traffic["time"] = seconds(traffic.event_time)
    traffic["arrival"] = seconds(traffic.receive_time)
    histories = {int(k): g.sort_values("time") for k, g in traffic.groupby("tr_id")}
    xs, sequences = [], []
    for r in points.itertuples():
        g = histories.get(int(r.tr_id))
        telemetry = []
        if g is not None:
            ts = g.time.to_numpy()
            window = g.iloc[
                np.searchsorted(ts, r.now - 900) : np.searchsorted(
                    ts, r.now, side="right"
                )
            ]
            telemetry = [
                TelemetryPoint(
                    timestamp=datetime.fromtimestamp(p.time, UTC),
                    packet_time=datetime.fromtimestamp(
                        p.arrival if policy == "receive" else p.time, UTC
                    ),
                    longitude=p.lon,
                    latitude=p.lat,
                    speed=p.speed,
                    course=p.heading,
                    location_valid=bool(p.location_valid),
                    is_historical=False,
                )
                for p in window.itertuples()
            ]
        request = MLPredictionRequest(
            tr_id=r.tr_id,
            target_stop_id=r.target_stop_id,
            current_time_T=datetime.fromtimestamp(r.now, UTC),
            target_time_begin=datetime.fromtimestamp(r.target_time, UTC),
            cur_dev_s=r.cur_dev_s,
            aggregates={
                "segment_avg_speed": 0,
                "idle_time_s": 0,
                "coverage_ratio": 0,
            },
            window={
                "start_time": datetime.fromtimestamp(r.now - 900, UTC),
                "end_time": datetime.fromtimestamp(r.now, UTC),
                "recent_points": telemetry,
            }
        )
        xs.append(features(request))
        if include_sequence:
            sequences.append(sequence(request))
    x = pd.DataFrame(xs)
    return points, x, np.asarray(sequences, dtype=np.float32)


def sequence(request):
    now = timestamp(request.current_time_T)
    result = np.zeros((6, 60), dtype=np.float32)
    for t, lon, lat, speed, course in history(request):
        index = min(59, int((t - (now - 900)) / 15))
        result[:, index] = (
            speed / 100,
            math.sin(math.radians(course)),
            math.cos(math.radians(course)),
            float(speed < 3),
            (now - t) / 900,
            1,
        )
    return result


def export(root, split, output, policy="receive"):
    points, x, _ = load(root, split, policy=policy, include_sequence=False)
    if "target_delay_s" not in points:
        raise ValueError("Updates require observed labels")
    result = x.copy()
    result["sample_id"] = points.sample_id
    result["now"] = points.now
    result["available_at"] = np.maximum(
        points.target_time, points.target_time + points.target_delay_s
    )
    result["target_delay_s"] = points.target_delay_s
    result["feature_version"] = FEATURE_VERSION
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT)
    parser.add_argument("--split", choices=["train", "test"], default="train")
    parser.add_argument("--policy", choices=["event", "receive"], default="receive")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.dataset, args.split, args.output, args.policy)
