import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error
from sklearn.model_selection import GroupKFold

from commons.ml_features import FEATURE_VERSION
from research.data.dataset import load
from research.models.tcn import fit_predict


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
        thread_count=2,
        verbose=False,
        allow_writing_files=False,
    )


def predict(m, x, mode):
    return m.predict(x) + (
        x.cur_dev_s.fillna(0).to_numpy() if mode == "residual" else 0
    )


def metrics(y, p, points, x):
    return {
        "mae": mae(y, p),
        "by_vehicle": {
            str(k): mae(y[g.index], p[g.index])
            for k, g in points.reset_index(drop=True).groupby("tr_id")
        },
        "by_class": {
            str(k): mae(y[g.index], p[g.index])
            for k, g in points.reset_index(drop=True).groupby("target_class")
        },
        "by_gps_age": {
            name: mae(y[mask], p[mask])
            for name, mask in [
                ("fresh", x.gps_age_s.to_numpy() <= 60),
                ("stale", x.gps_age_s.to_numpy() > 60),
            ]
            if mask.any()
        },
    }


def run(root, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    p, x, seq, gps = load(root, "train")
    real = p.tr_id < 1000000
    print("Vehicle IDs:", sorted(p.tr_id.unique()), flush=True)
    print("Real rows:", int(real.sum()), flush=True)
    p, x, seq, gps = (
        p[real].reset_index(drop=True),
        x[real].reset_index(drop=True),
        seq[real],
        gps[real].reset_index(drop=True),
    )
    y = p.target_delay_s.to_numpy()
    hint = x.cur_dev_s.fillna(0).to_numpy()
    folds = list(GroupKFold(3).split(x, y, p.tr_id))
    boundary = float(p.now.quantile(0.7))
    actual_arrival = p.target_time + p.target_delay_s
    train_idx = np.flatnonzero(
        (p.now < boundary - 1800) & (actual_arrival < boundary - 900)
    )
    val_idx = np.flatnonzero(p.now >= boundary)
    all_folds = folds + [(train_idx, val_idx)]
    configs = [
        {"depth": d, "learning_rate": lr, "l2_leaf_reg": reg, "iterations": 700}
        for d, lr, reg in [(4, 0.03, 10), (5, 0.05, 20), (6, 0.08, 30)]
    ]
    basic = [
        "cur_dev_s",
        "cur_dev_missing",
        "horizon_s",
        "hour_sin",
        "hour_cos",
        "stops_ahead",
    ]
    motion = [
        c for c in x if c not in ["target_lon", "target_lat", "distance_target_m"]
    ]
    experiments = []
    cache = {}
    for cols_name, cols in [("basic", basic), ("motion", motion), ("spatial", list(x))]:
        for mode in ["direct", "residual"]:
            for config in configs:
                oof = np.full(len(x), np.nan)
                errors = []
                trees = []
                for i, (tr, va) in enumerate(all_folds):
                    m = model(config)
                    target = y - (hint if mode == "residual" else 0)
                    m.fit(
                        x.iloc[tr][cols],
                        target[tr],
                        eval_set=(x.iloc[va][cols], target[va]),
                        early_stopping_rounds=70,
                    )
                    pred = predict(m, x.iloc[va][cols], mode)
                    errors.append(mae(y[va], pred))
                    trees.append(m.tree_count_)
                    if i < 3:
                        oof[va] = pred
                score = (mae(y, oof) + errors[-1]) / 2
                record = {
                    "features": cols_name,
                    "mode": mode,
                    "config": config,
                    "group_mae": mae(y, oof),
                    "time_mae": errors[-1],
                    "selection_mae": score,
                    "trees": trees,
                }
                experiments.append(record)
                cache[len(experiments) - 1] = (oof, cols)
                print(record, flush=True)
    best_idx = min(
        range(len(experiments)), key=lambda i: experiments[i]["selection_mae"]
    )
    best = experiments[best_idx]
    oof, cols = cache[best_idx]
    iterations = max(30, int(np.median(best["trees"])))
    tcn_oof = np.zeros(len(x))
    tcn_time = None
    for i, (tr, va) in enumerate(all_folds):
        _, pred = fit_predict(seq, hint, y, tr, va)
        if i < 3:
            tcn_oof[va] = pred
        else:
            tcn_time = mae(y[va], pred)
    blends = {
        str(w): mae(y, (1 - w) * oof + w * tcn_oof) for w in [0, 0.1, 0.25, 0.5, 1.0]
    }
    tcn, _ = fit_predict(seq, hint, y, np.arange(len(x)), np.arange(len(x)))
    import torch

    torch.save(tcn.state_dict(), out / "tcn.pt")
    final = model(best["config"], iterations)
    final.fit(x[cols], y - (hint if best["mode"] == "residual" else 0))
    final.save_model(str(out / "delay.cbm"))
    late = (y > 120).astype(int)
    probs = np.zeros(len(x))
    for tr, va in folds:
        c = CatBoostClassifier(
            iterations=200,
            depth=4,
            learning_rate=0.03,
            l2_leaf_reg=20,
            thread_count=2,
            verbose=False,
            random_seed=42,
            allow_writing_files=False,
        )
        c.fit(x.iloc[tr][cols], late[tr])
        probs[va] = c.predict_proba(x.iloc[va][cols])[:, 1]
    logits = np.log(
        np.clip(probs, 1e-06, 1 - 1e-06) / (1 - np.clip(probs, 1e-06, 1 - 1e-06))
    )[:, None]
    calibration = LogisticRegression(C=0.1).fit(logits, late)
    calibrated = np.zeros(len(x))
    for tr, va in folds:
        cal = LogisticRegression(C=0.1).fit(logits[tr], late[tr])
        calibrated[va] = cal.predict_proba(logits[va])[:, 1]
    threshold_scores = {}
    for threshold in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
        alarm = calibrated >= threshold
        tp = int((alarm & (late == 1)).sum())
        fp = int((alarm & (late == 0)).sum())
        fn = int((~alarm & (late == 1)).sum())
        threshold_scores[str(threshold)] = 2 * tp / max(1, 2 * tp + fp + fn)
    threshold = float(max(threshold_scores, key=threshold_scores.get))
    c.fit(x[cols], late)
    c.save_model(str(out / "late.cbm"))
    interval = float(np.quantile(np.abs(y - oof), 0.8))
    metadata = {
        "feature_version": FEATURE_VERSION,
        "features": cols,
        "mode": best["mode"],
        "config": best["config"],
        "iterations": iterations,
        "calibration_coef": float(calibration.coef_[0, 0]),
        "calibration_intercept": float(calibration.intercept_[0]),
        "risk_threshold": threshold,
        "interval_radius_s": interval,
        "model_version": "catboost-v1",
        "training_rows": len(x),
        "tcn_weight": 0,
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    pt, xt, _st, gpst = load(root, "test")
    yt = pt.target_delay_s.to_numpy()
    prediction = predict(final, xt[cols], best["mode"])
    probability = c.predict_proba(xt[cols])[:, 1]
    probability = calibration.predict_proba(
        np.log(
            np.clip(probability, 1e-06, 1 - 1e-06)
            / (1 - np.clip(probability, 1e-06, 1 - 1e-06))
        )[:, None]
    )[:, 1]
    delta = np.abs(yt - xt.cur_dev_s.to_numpy()) - np.abs(yt - prediction)
    groups = [delta[pt.tr_id.to_numpy() == k] for k in pt.tr_id.unique()]
    rng = np.random.default_rng(42)
    boot = [
        np.concatenate(
            [groups[i] for i in rng.integers(0, len(groups), len(groups))]
        ).mean()
        for _ in range(1000)
    ]
    timings = []
    for _ in range(250):
        start = time.perf_counter()
        final.predict(xt[cols].iloc[:1], thread_count=1)
        timings.append((time.perf_counter() - start) * 1000)
    report = {
        "hardware": platform.platform() + " " + platform.machine(),
        "real_id_rule": "tr_id < 1000000; synthetic provenance unknown, excluded",
        "train_rows": len(p),
        "train_vehicles": int(p.tr_id.nunique()),
        "experiments": experiments,
        "selected": best,
        "validation": "3 held-out vehicle folds + forward time split purged by target availability and 15-minute history",
        "forward_split": {
            "train": len(train_idx),
            "validation": len(val_idx),
            "boundary": boundary,
        },
        "baseline_test": {
            "zero": mae(yt, np.zeros(len(yt))),
            "median": mae(yt, np.full(len(yt), np.median(y))),
            "persistence": mae(yt, xt.cur_dev_s),
        },
        "test": metrics(yt, prediction, pt, xt),
        "improvement_vehicle_bootstrap_95": np.quantile(boot, [0.025, 0.975]).tolist(),
        "gps_reconstructed_test_mae": mae(yt, predict(final, gpst[cols], best["mode"])),
        "gps_reconstructed_coverage": float((gpst.cur_dev_missing == 0).mean()),
        "tcn": {
            "group_mae": mae(y, tcn_oof),
            "time_mae": tcn_time,
            "blend_group_mae": blends,
            "deployed": False,
        },
        "probability_test": {
            "brier": float(brier_score_loss(yt > 120, probability)),
            "logloss": float(log_loss(yt > 120, probability)),
            "bins": [
                {
                    "n": int(((probability >= lo) & (probability < lo + 0.2)).sum()),
                    "predicted": float(
                        probability[
                            (probability >= lo) & (probability < lo + 0.2)
                        ].mean()
                    ),
                    "observed": float(
                        (
                            yt[(probability >= lo) & (probability < lo + 0.2)] > 120
                        ).mean()
                    ),
                }
                for lo in np.arange(0, 1, 0.2)
                if ((probability >= lo) & (probability < lo + 0.2)).any()
            ],
        },
        "interval_test_coverage": float((np.abs(yt - prediction) <= interval).mean()),
        "risk_threshold_f1": threshold_scores,
        "model_latency_ms": dict(
            zip(["p50", "p95", "p99"], np.quantile(timings, [0.5, 0.95, 0.99]).tolist())
        ),
        "dataset_sha256": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in Path(root).rglob("*.csv")
        },
        "limitations": [
            "One day only; test overlaps train vehicles/time.",
            "Synthetic provenance unknown; no synthetic rows used.",
            "Neighbour context not deployed: matching route geometry unavailable.",
            "TCN retained only as experiment; no ensemble deployed.",
        ],
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    pd.DataFrame(
        {
            "sample_id": p.sample_id,
            "prediction": oof,
            "target": y,
            "tcn_prediction": tcn_oof,
            "late_probability": calibrated,
        }
    ).to_csv(out / "oof.csv", index=False)
    pd.DataFrame(
        {"sample_id": pt.sample_id, "prediction": prediction, "target": yt}
    ).to_csv(out / "test_predictions.csv", index=False)
    pv, xv, _, _ = load(root, "validate")
    pred = predict(final, xv[cols], best["mode"])
    submission = pd.DataFrame({"sample_id": pv.sample_id, "prediction": pred})
    assert (
        len(submission) == 151
        and submission.sample_id.is_unique
        and np.isfinite(pred).all()
    )
    template = pd.read_csv(Path(root) / "sample_submission.csv", sep=";")
    assert set(template.sample_id) == set(submission.sample_id)
    submission.set_index("sample_id").loc[template.sample_id].reset_index().to_csv(
        out / "submission.csv", sep=";", index=False
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "selected",
                    "baseline_test",
                    "test",
                    "tcn",
                    "gps_reconstructed_test_mae",
                    "model_latency_ms",
                ]
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset")
    parser.add_argument("--output", default="ml/artifacts")
    args = parser.parse_args()
    run(args.dataset, args.output)
