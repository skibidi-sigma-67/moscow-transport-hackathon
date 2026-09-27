import json
from pathlib import Path

import numpy as np
from catboost import CatBoostClassifier
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.model_selection import GroupKFold

from research.data.dataset import load
from research.training.train import mae, model


def run():
    p, _, _, x = load("dataset", "train")
    real = p.tr_id < 1000000
    p, x = (p[real].reset_index(drop=True), x[real].reset_index(drop=True))
    y = p.target_delay_s.to_numpy()
    folds = list(GroupKFold(3).split(x, y, p.tr_id))
    boundary = p.now.quantile(0.7)
    folds.append(
        (
            np.flatnonzero(
                (p.now < boundary - 1800) & (p.target_time + y < boundary - 900)
            ),
            np.flatnonzero(p.now >= boundary),
        )
    )
    candidates = []
    for depth in [4, 6]:
        for features in ["basic", "full"]:
            cols = (
                [
                    "cur_dev_s",
                    "cur_dev_missing",
                    "horizon_s",
                    "hour_sin",
                    "hour_cos",
                    "stops_ahead",
                ]
                if features == "basic"
                else list(x)
            )
            cfg = {
                "depth": depth,
                "learning_rate": 0.05,
                "l2_leaf_reg": 30,
                "iterations": 500,
            }
            errors = []
            trees = []
            oof = np.zeros(len(x))
            for i, (tr, va) in enumerate(folds):
                m = model(cfg)
                m.fit(
                    x.iloc[tr][cols],
                    y[tr],
                    eval_set=(x.iloc[va][cols], y[va]),
                    early_stopping_rounds=60,
                )
                pred = m.predict(x.iloc[va][cols])
                errors.append(mae(y[va], pred))
                trees.append(m.tree_count_)
                if i < 3:
                    oof[va] = pred
            candidates.append(
                {
                    "config": cfg,
                    "features": cols,
                    "group_mae": mae(y, oof),
                    "time_mae": errors[-1],
                    "score": (mae(y, oof) + errors[-1]) / 2,
                    "iterations": max(20, int(np.median(trees))),
                    "radius": float(np.quantile(abs(y - oof), 0.8)),
                }
            )
    best = min(candidates, key=lambda c: c["score"])
    m = model(best["config"], best["iterations"])
    m.fit(x[best["features"]], y)
    m.save_model("ml/artifacts/gps_delay.cbm")
    c = CatBoostClassifier(
        iterations=150,
        depth=4,
        learning_rate=0.03,
        l2_leaf_reg=30,
        verbose=False,
        thread_count=2,
        random_seed=42,
        allow_writing_files=False,
    )
    c.fit(x[best["features"]], y > 120)
    c.save_model("ml/artifacts/gps_late.cbm")
    pt, _, _, xt = load("dataset", "test")
    yt = pt.target_delay_s.to_numpy()
    pred = m.predict(xt[best["features"]])
    prob = c.predict_proba(xt[best["features"]])[:, 1]
    report = {
        "candidates": candidates,
        "selected": best,
        "test_mae": mae(yt, pred),
        "brier": float(brier_score_loss(yt > 120, prob)),
        "logloss": float(log_loss(yt > 120, prob)),
        "interval_coverage": float((abs(yt - pred) <= best["radius"]).mean()),
        "note": "GPS probabilities are uncalibrated; this branch is always DEGRADED. Radius=75m engineering default, not proven optimal.",
    }
    Path("ml/artifacts/gps_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
