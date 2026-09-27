from pathlib import Path

import numpy as np
import pandas as pd

from research.legacy_features import (
    Observation,
    Stop,
    features,
    reconstruct_deviation,
    sequence,
)


def seconds(values):
    return (
        pd.to_datetime(values, format="mixed", utc=True)
        .dt.as_unit("ns")
        .astype("int64")
        / 1000000000.0
    )


def load(root, split, include_extras=False):
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
    points["target_time"] = seconds(points["target_time_begin"])
    schedule = pd.read_csv(
        root / split / ("schedule_plan.csv" if split == "validate" else "schedule.csv"),
        usecols=["tr_id", "tt_action_item_id", "time_begin", "geom"],
    )
    schedule["time"] = seconds(schedule["time_begin"])
    coords = schedule.geom.str.extract(
        "POINT\\s*\\(([-\\d.]+)\\s+([-\\d.]+)\\)"
    ).astype(float)
    schedule["lon"], schedule["lat"] = (coords[0], coords[1])
    plans = {
        int(k): [
            Stop(r.time, r.lon, r.lat, int(r.tt_action_item_id)) for r in g.itertuples()
        ]
        for k, g in schedule.groupby("tr_id")
    }
    traffic = pd.read_csv(
        root / split / "traffic.csv",
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
    xs, seqs, gps_xs = ([], [], [])
    for r in points.itertuples():
        g = histories.get(int(r.tr_id))
        if g is None:
            history = []
        else:
            ts = g.time.to_numpy()
            window = g.iloc[
                np.searchsorted(ts, r.now - 900) : np.searchsorted(
                    ts, r.now, side="right"
                )
            ]
            history = [
                Observation(
                    p.time, p.lon, p.lat, p.speed, p.heading, bool(p.location_valid)
                )
                for p in window.itertuples()
            ]
        stops = plans.get(int(r.tr_id), [])
        target = next(
            (s for s in stops if s.stop_id == r.target_stop_id),
            Stop(r.target_time, np.nan, np.nan, int(r.target_stop_id)),
        )
        if not 600 < target.time - r.now <= 900:
            raise ValueError(f"Invalid target horizon: {r.sample_id}")
        hint = float(r.cur_dev_s) if pd.notna(r.cur_dev_s) else None
        xs.append(features(history, stops, target, r.now, hint))
        if include_extras:
            recovered, _ = reconstruct_deviation(history, stops, r.now)
            gps_xs.append(features(history, stops, target, r.now, recovered))
            seqs.append(sequence(history, r.now))
    return (
        points,
        pd.DataFrame(xs),
        np.asarray(seqs, dtype=np.float32).transpose(0, 2, 1)
        if include_extras
        else None,
        pd.DataFrame(gps_xs) if include_extras else None,
    )
