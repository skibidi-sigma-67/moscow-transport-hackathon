import hashlib
import json
from pathlib import Path

import pandas as pd

from research.data.dataset import seconds


def run():
    root = Path("dataset")
    result = {}
    for split in ["train", "test", "validate"]:
        traffic = pd.read_csv(root / split / "traffic.csv")
        points = pd.read_csv(
            root
            / (
                f"labels/labels_{split}.csv"
                if split != "validate"
                else "validate/points.csv"
            )
        )
        arrivals = seconds(traffic.receive_time)
        events = seconds(traffic.event_time)
        result[split] = {
            "points": len(points),
            "vehicles": int(points.tr_id.nunique()),
            "traffic_rows": len(traffic),
            "duplicate_sample_ids": int(points.sample_id.duplicated().sum()),
            "duplicate_events": int(traffic.duplicated(["tr_id", "event_time"]).sum()),
            "invalid_location": int((~traffic.location_valid).sum()),
            "impossible_speed": int((traffic.speed > 130).sum()),
            "negative_delivery_delay": int((arrivals < events).sum()),
            "late_delivery_over_60s": int((arrivals - events > 60).sum()),
            "horizon_min": float(
                (seconds(points.target_time_begin) - seconds(points["T"])).min()
            ),
            "horizon_max": float(
                (seconds(points.target_time_begin) - seconds(points["T"])).max()
            ),
        }
    result["test_validate_traffic_identical"] = (
        hashlib.sha256((root / "test/traffic.csv").read_bytes()).hexdigest()
        == hashlib.sha256((root / "validate/traffic.csv").read_bytes()).hexdigest()
    )
    schedule = pd.read_csv(root / "train/schedule.csv", usecols=["tt_action_item_id"])
    result["train_schedule_contains_target_ids"] = {
        split: int(
            pd.read_csv(
                root
                / (
                    f"labels/labels_{split}.csv"
                    if split == "test"
                    else "validate/points.csv"
                )
            )
            .target_stop_id.isin(schedule.tt_action_item_id)
            .sum()
        )
        for split in ["test", "validate"]
    }
    result["policy"] = (
        "Schedule actual arrivals excluded structurally; validate labels never recovered. Synthetic lineage unavailable; synthetic rows excluded."
    )
    Path("ml/artifacts/audit.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    run()
