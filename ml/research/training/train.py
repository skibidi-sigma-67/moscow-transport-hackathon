import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from ml.features import FEATURE_VERSION
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold

from research.data.dataset import OUTPUT, ROOT, load


def mae(y, p):
    return float(mean_absolute_error(y, p))


def model(config, iterations=None):
    return CatBoostRegressor(
        loss_function="MAE",
        iterations=iterations or config["iterations"],
        depth=config["depth"],
        learning_rate=config["learning_rate"],
        l2_leaf_reg=config["l2_leaf_reg"],
        random_seed=42,
        thread_count=4,
        verbose=False,
        allow_writing_files=False,
    )


def predict(m, x, mode):
    return m.predict(x, thread_count=1) + (
        x.cur_dev_s.to_numpy() if mode == "residual" else 0
    )


def mask_hint(x):
    x = x.copy()
    x["cur_dev_s"] = 0.0
    if "cur_dev_zero" in x:
        x["cur_dev_zero"] = 1.0
    if "cur_dev_per_horizon" in x:
        x["cur_dev_per_horizon"] = 0.0
    return x


def splits(p):
    folds = [("vehicle", a, b) for a, b in GroupKFold(3).split(p, groups=p.tr_id)]
    boundaries = [float(p.now.quantile(q)) for q in (0.5, 0.65, 0.8)]
    for i, boundary in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else float("inf")
        a = np.flatnonzero(
            (p.now < boundary - 1800)
            & (
                np.maximum(p.target_time, p.target_time + p.target_delay_s)
                < boundary - 900
            )
        )
        b = np.flatnonzero((p.now >= boundary) & (p.now < end))
        if not len(a) or not len(b):
            raise ValueError("Insufficient data for forward validation")
        folds.append(("time", a, b))
    return folds


def fit(config, x, y, mode, augmentation=0.0):
    target = y - x.cur_dev_s.to_numpy() if mode == "residual" else y
    weights = np.ones(len(x))
    if augmentation:
        extra = mask_hint(x)
        x = pd.concat([x, extra], ignore_index=True)
        target = np.concatenate([target, y])
        weights = np.concatenate([weights, np.full(len(y), augmentation)])
    m = model(config)
    m.fit(
        x,
        target,
        sample_weight=weights,
        cat_features=["vehicle"] if "vehicle" in x else [],
    )
    return m


def evaluate(p, x, xr, folds, config, cols, mode, augmentation=0.0):
    y = p.target_delay_s.to_numpy()
    errors = {"vehicle": [], "time": []}
    receive_errors, missing_errors = [], []
    oof = np.zeros(len(p))
    for kind, tr, va in folds:
        m = fit(config, x.iloc[tr][cols], y[tr], mode, augmentation)
        pred = predict(m, x.iloc[va][cols], mode)
        errors[kind].extend(abs(y[va] - pred).tolist())
        if kind == "vehicle":
            oof[va] = pred
        else:
            receive_errors.extend(
                abs(y[va] - predict(m, xr.iloc[va][cols], mode)).tolist()
            )
            missing_errors.extend(
                abs(y[va] - predict(m, mask_hint(x.iloc[va][cols]), mode)).tolist()
            )
    record = {
        "config": config,
        "features": cols,
        "mode": mode,
        "augmentation": augmentation,
        "group_mae": float(np.mean(errors["vehicle"])),
        "time_mae": float(np.mean(errors["time"])),
        "receive_time_mae": float(np.mean(receive_errors)),
        "missing_hint_mae": float(np.mean(missing_errors)),
    }
    record["selection_mae"] = (record["group_mae"] + record["time_mae"]) / 2
    return record, oof


def run(root, out):
    root, out = Path(root), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    p, x, _ = load(root, "train", include_sequence=False)
    _, xr, _ = load(root, "train", policy="receive", include_sequence=False)
    real = p.tr_id < 1000000
    p, x, xr = [v[real].reset_index(drop=True) for v in (p, x, xr)]
    y = p.target_delay_s.to_numpy()
    folds = splits(p)
    basic = ["cur_dev_s", "horizon_s", "hour_sin", "hour_cos"]
    new = [
        c
        for c in x
        if c.startswith(
            (
                "time_",
                "safe_",
                "current_stop",
                "since_moving",
                "stop_count",
                "gps_jumps",
            )
        )
    ]
    legacy = [c for c in x if c not in new]
    weighted = (
        basic + ["gps_age_s", "cur_dev_zero", "cur_dev_per_horizon", "last_speed"] + new
    )
    experiments, predictions = [], []
    configs = [
        {"depth": d, "learning_rate": lr, "l2_leaf_reg": reg, "iterations": n}
        for d, lr, reg, n in [
            (3, 0.05, 3, 192),
            (4, 0.05, 3, 194),
            (4, 0.08, 20, 128),
            (5, 0.05, 20, 192),
            (3, 0.1, 10, 128),
            (5, 0.08, 3, 256),
        ]
    ]
    for cols in [
        legacy,
        weighted,
        weighted + ["vehicle", "longitude", "latitude"],
        list(x),
    ]:
        for mode in ["direct", "residual"]:
            for config in configs:
                record, oof = evaluate(p, x, xr, folds, config, cols, mode)
                experiments.append(record)
                predictions.append(oof)
                print(
                    json.dumps({k: v for k, v in record.items() if k != "features"}),
                    flush=True,
                )
    top = sorted(
        range(len(experiments)), key=lambda i: experiments[i]["selection_mae"]
    )[:3]
    for i in top:
        old = experiments[i]
        record, oof = evaluate(
            p, x, xr, folds, old["config"], old["features"], old["mode"], 0.15
        )
        experiments.append(record)
        predictions.append(oof)
        print(
            json.dumps({k: v for k, v in record.items() if k != "features"}), flush=True
        )
    best_score = min(e["selection_mae"] for e in experiments)
    eligible = [
        i for i, e in enumerate(experiments) if e["selection_mae"] <= best_score + 0.25
    ]
    index = min(
        eligible,
        key=lambda i: (
            experiments[i]["config"]["iterations"] * experiments[i]["config"]["depth"],
            len(experiments[i]["features"]),
            experiments[i]["selection_mae"],
        ),
    )
    best = experiments[index]
    cols, mode = best["features"], best["mode"]
    start = time.perf_counter()
    final = fit(best["config"], x[cols], y, mode, best["augmentation"])
    fit_seconds = time.perf_counter() - start
    final.save_model(str(out / "delay.cbm"))
    meta = {
        "feature_version": FEATURE_VERSION,
        "features": cols,
        "mode": mode,
        "config": best["config"],
        "iterations": final.tree_count_,
        "augmentation": best["augmentation"],
        "model_version": "catboost-motion-v5",
        "training_rows": len(p),
        "training_sample_ids": p.sample_id.tolist(),
        "training_max_time": float(p.now.max()),
        "training_labels_available_at": float(
            np.maximum(p.target_time, p.target_time + y).max()
        ),
        "update_tree_cap": 256,
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2))
    pt, xt, _ = load(root, "test", include_sequence=False)
    _, xrt, _ = load(root, "test", policy="receive", include_sequence=False)
    yt = pt.target_delay_s.to_numpy()
    pred = predict(final, xt[cols], mode)
    report = {
        "selected": best,
        "experiments": experiments,
        "train_rows": len(p),
        "train_vehicles": int(p.tr_id.nunique()),
        "fit_seconds": fit_seconds,
        "validation": "3 held-out vehicle folds and 3 non-overlapping forward windows, target-availability purge; test excluded from selection",
        "selection_rule": "Within 0.25 seconds of best validation MAE choose smallest tree-depth budget, then feature count",
        "folds": [
            {
                "kind": k,
                "train": len(a),
                "validation": len(b),
                "validation_start": float(p.now.iloc[b].min()),
            }
            for k, a, b in folds
        ],
        "test": {
            "mae": mae(yt, pred),
            "persistence_mae": mae(yt, xt.cur_dev_s),
            "receive_mae": mae(yt, predict(final, xrt[cols], mode)),
            "missing_hint_mae": mae(yt, predict(final, mask_hint(xt[cols]), mode)),
        },
        "dataset_sha256": {
            str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in root.rglob("*.csv")
        },
        "limitations": [
            "One day only; test has already been inspected in previous iterations and is not a fresh holdout",
            "Platform score unknown",
            "No contract flag distinguishes unknown deviation from genuine zero",
            "Synthetic vehicles excluded",
            "Tree budget is a latency proxy; end-to-end latency measured separately",
        ],
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    pd.DataFrame(
        {"sample_id": p.sample_id, "prediction": predictions[index], "target": y}
    ).to_csv(out / "oof.csv", index=False)
    pd.DataFrame({"sample_id": pt.sample_id, "prediction": pred, "target": yt}).to_csv(
        out / "test_predictions.csv", index=False
    )
    pv, xv, _ = load(root, "validate", include_sequence=False)
    submission = pd.DataFrame(
        {"sample_id": pv.sample_id, "prediction": predict(final, xv[cols], mode)}
    )
    template = pd.read_csv(root / "sample_submission.csv", sep=";")
    if (
        not submission.sample_id.is_unique
        or set(submission.sample_id) != set(template.sample_id)
        or not np.isfinite(submission.prediction).all()
    ):
        raise ValueError("Invalid submission")
    submission.set_index("sample_id").loc[template.sample_id].reset_index().to_csv(
        out / "submission.csv", sep=";", index=False
    )
    print(json.dumps(report["test"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.dataset, args.output)
