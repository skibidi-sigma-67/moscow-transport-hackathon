import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from ml.features import FEATURE_VERSION
from ml.models.predictor import Predictor

from research.data.dataset import OUTPUT
from research.training.train import mae, model, predict


def read_batch(path, columns):
    data = pd.read_csv(path, dtype={"vehicle": str, "sample_id": str})
    required = columns + [
        "sample_id",
        "now",
        "available_at",
        "target_delay_s",
        "feature_version",
    ]
    if not set(required).issubset(data) or data.empty:
        raise ValueError(
            "Batch must contain features, IDs, timestamps, labels and feature_version"
        )
    if data.sample_id.isna().any() or not data.sample_id.is_unique:
        raise ValueError("Batch sample IDs must be unique and non-null")
    if not (data.feature_version == FEATURE_VERSION).all():
        raise ValueError("Incompatible batch feature version")
    numeric = data[[c for c in required if c not in ("vehicle", "sample_id")]]
    if (
        np.isinf(numeric.to_numpy(dtype=float)).any()
        or not np.isfinite(data[["now", "available_at", "target_delay_s", "cur_dev_s"]])
        .all()
        .all()
    ):
        raise ValueError("Invalid batch numbers")
    if (data.available_at < data.now).any():
        raise ValueError("Labels must become available after prediction time")
    return data


def update(
    directory,
    batch_path,
    validation_path,
    out,
    replay_path=None,
    trees=32,
    max_rows=4000,
    min_gain=0.5,
):
    started = time.perf_counter()
    directory, out = Path(directory), Path(out)
    if out.exists():
        raise ValueError("Output must be a new version directory")
    if (
        not 1 <= trees <= 64
        or max_rows < 40
        or not np.isfinite(min_gain)
        or min_gain < 0
    ):
        raise ValueError("Invalid update budget")
    parent = Predictor(directory)
    meta = parent.meta
    if meta["feature_version"] != FEATURE_VERSION or "training_sample_ids" not in meta:
        raise ValueError("Retrain once to establish update provenance")
    cols, mode = meta["features"], meta["mode"]
    batch = read_batch(batch_path, cols)
    valid = read_batch(validation_path, cols)
    replay = read_batch(replay_path, cols) if replay_path else batch.iloc[:0].copy()
    previous_ids = set(meta["training_sample_ids"])
    if set(batch.sample_id) & previous_ids:
        raise ValueError("New batch contains samples already used by the parent")
    if set(valid.sample_id) & (
        previous_ids
        | set(meta.get("selection_sample_ids", []))
        | set(batch.sample_id)
        | set(replay.sample_id)
    ):
        raise ValueError("Validation overlaps training samples")
    if set(replay.sample_id) & set(batch.sample_id):
        raise ValueError("Replay overlaps the new batch")
    boundary = float(valid.now.min())
    all_training = pd.concat([batch, replay], ignore_index=True)
    if (
        meta["training_labels_available_at"] >= boundary
        or meta["training_max_time"] >= boundary - 900
        or meta.get("selection_labels_available_at", 0) >= boundary
        or all_training.available_at.max() >= boundary
        or all_training.now.max() >= boundary - 900
    ):
        raise ValueError(
            "Validation must follow all training labels with a 900-second telemetry purge"
        )
    if len(valid) < 20 or len(batch) < 10:
        raise ValueError("At least 10 new samples and 20 validation samples required")
    batch_limit = max_rows if replay.empty else max_rows // 2
    batch = batch.sort_values("now").tail(batch_limit)
    replay = replay.sample(n=min(len(replay), max_rows - len(batch)), random_state=42)
    train = pd.concat([batch, replay], ignore_index=True)
    y = train.target_delay_s.to_numpy()
    target = y - train.cur_dev_s.to_numpy() if mode == "residual" else y
    budget = min(256, int(meta.get("update_tree_cap", 256)))
    remaining = budget - parent.regressor.tree_count_
    if remaining > 0:
        count = min(trees, remaining)
        initial = parent.regressor
        method = "append"
    else:
        if replay.empty:
            raise ValueError(
                "Tree cap reached: provide representative replay for bounded refit"
            )
        count = min(128, budget)
        initial = None
        method = "bounded_refit"
    config = dict(meta["config"], iterations=count)
    candidate = model(config)
    fit_start = time.perf_counter()
    candidate.fit(
        train[cols],
        target,
        cat_features=["vehicle"] if "vehicle" in cols else [],
        init_model=initial,
        sample_weight=np.concatenate([np.ones(len(batch)), np.full(len(replay), 0.5)]),
    )
    fit_seconds = time.perf_counter() - fit_start
    yt = valid.target_delay_s.to_numpy()
    before = predict(parent.regressor, valid[cols], mode)
    after = predict(candidate, valid[cols], mode)
    baseline, updated = mae(yt, before), mae(yt, after)
    accepted = updated <= baseline - min_gain
    out.mkdir(parents=True)
    report = {
        "accepted": accepted,
        "method": method,
        "parent_mae": baseline,
        "candidate_mae": updated,
        "min_gain_s": min_gain,
        "fit_seconds": fit_seconds,
        "elapsed_seconds": time.perf_counter() - started,
        "training_rows": len(train),
        "new_rows": len(batch),
        "replay_rows": len(replay),
        "validation_rows": len(valid),
        "parent_trees": parent.regressor.tree_count_,
        "candidate_trees": candidate.tree_count_,
        "tree_cap": budget,
        "batch_sha256": hashlib.sha256(Path(batch_path).read_bytes()).hexdigest(),
        "validation_sha256": hashlib.sha256(
            Path(validation_path).read_bytes()
        ).hexdigest(),
        "replay_sha256": hashlib.sha256(Path(replay_path).read_bytes()).hexdigest()
        if replay_path
        else None,
        "limitations": "Acceptance uses this validation set; assess future generalization on the next unseen time window. No automatic deployment.",
    }
    if accepted:
        candidate.save_model(str(out / "delay.cbm"))
        meta = dict(
            meta,
            config=dict(config, iterations=candidate.tree_count_),
            iterations=candidate.tree_count_,
            model_version=meta["model_version"] + "-update",
            training_sample_ids=sorted(previous_ids | set(train.sample_id)),
            selection_sample_ids=sorted(
                set(meta.get("selection_sample_ids", [])) | set(valid.sample_id)
            ),
            selection_labels_available_at=float(valid.available_at.max()),
            training_rows=len(previous_ids | set(train.sample_id)),
            training_max_time=max(meta["training_max_time"], float(train.now.max())),
            training_labels_available_at=max(
                meta["training_labels_available_at"], float(train.available_at.max())
            ),
        )
        (out / "metadata.json").write_text(json.dumps(meta, indent=2))
    report["elapsed_seconds"] = time.perf_counter() - started
    (out / "update_report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False)
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=OUTPUT)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trees", type=int, default=32)
    parser.add_argument("--max-rows", type=int, default=4000)
    args = parser.parse_args()
    print(
        json.dumps(
            update(
                args.model,
                args.batch,
                args.validation,
                args.output,
                args.replay,
                args.trees,
                args.max_rows,
            ),
            indent=2,
        )
    )
