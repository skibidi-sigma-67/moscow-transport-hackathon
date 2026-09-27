import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.model_selection import GroupKFold

from research.data.dataset import OUTPUT, ROOT
from research.legacy_dataset import load
from research.training.legacy_upgrade import FEATURES, mae


def fit(train_x, train_y, extra_x, extra_y, columns, trees, weight, depth=6):
    x = pd.concat((train_x[columns], extra_x[columns]), ignore_index=True)
    y = np.concatenate((train_y, extra_y))
    weights = np.concatenate((np.ones(len(train_y)), np.full(len(extra_y), weight)))
    model = CatBoostRegressor(
        loss_function="MAE",
        iterations=trees,
        depth=depth,
        learning_rate=0.08,
        l2_leaf_reg=30,
        random_seed=42,
        thread_count=2,
        verbose=False,
        allow_writing_files=False,
    )
    model.fit(x, y, sample_weight=weights)
    return model


def run(root, winner, reference, output):
    root, winner, reference, output = map(Path, (root, winner, reference, output))
    if output.exists():
        raise ValueError("Output must be a new candidate directory")
    output.mkdir(parents=True)
    train_p, train_x, _, _ = load(root, "train")
    real = train_p.tr_id < 1000000
    train_p, train_x = (
        train_p[real].reset_index(drop=True),
        train_x[real].reset_index(drop=True),
    )
    test_p, test_x, _, _ = load(root, "test")
    val_p, val_x, _, _ = load(root, "validate")
    train_y, test_y = (
        train_p.target_delay_s.to_numpy(),
        test_p.target_delay_s.to_numpy(),
    )
    previous = pd.read_csv(winner / "test_oof.csv")
    if not previous.sample_id.equals(test_p.sample_id):
        raise ValueError("Winner OOF row order differs from dataset")
    winner_group = previous.candidate.to_numpy()
    old = CatBoostRegressor()
    old.load_model(str(reference / "delay.cbm"))
    reference_test = old.predict(test_x[FEATURES])
    folds = list(GroupKFold(4).split(test_x, test_y, test_p.tr_id))
    boundary = float(test_p.now.quantile(0.7))
    early = np.flatnonzero(
        (test_p.now < boundary - 1800)
        & (np.maximum(test_p.target_time, test_p.target_time + test_y) < boundary - 900)
    )
    late = np.flatnonzero(test_p.now >= boundary)
    winner_meta = json.loads((winner / "metadata.json").read_text())
    winner_forward_model = fit(
        train_x,
        train_y,
        test_x.iloc[early],
        test_y[early],
        FEATURES,
        winner_meta["config"]["iterations"],
        winner_meta["config"]["test_weight"],
    )
    winner_time = (1 - winner_meta["blend"]) * reference_test[late] + winner_meta[
        "blend"
    ] * winner_forward_model.predict(test_x.iloc[late][FEATURES])
    baseline = {
        "group_mae": mae(test_y, winner_group),
        "time_mae": mae(test_y[late], winner_time),
    }
    baseline["selection_mae"] = (baseline["group_mae"] + baseline["time_mae"]) / 2
    sets = {
        "basic": FEATURES,
        "route": FEATURES + ["distance_target_m", "gps_age_s"],
        "route_location": FEATURES
        + ["target_lon", "target_lat", "distance_target_m", "gps_age_s"],
        "motion": FEATURES
        + ["gps_age_s", "speed_300", "idle_300", "coverage_300", "trend_300"],
        "route_motion": FEATURES
        + ["distance_target_m", "gps_age_s", "speed_300", "idle_300", "coverage_300"],
    }
    experiments = []
    for name, columns in sets.items():
        for trees, weight, depth in (
            (120, 8, 6),
            (160, 4, 6),
            (160, 8, 6),
            (120, 4, 5),
        ):
            oof = np.empty(len(test_p))
            for tr, va in folds:
                model = fit(
                    train_x,
                    train_y,
                    test_x.iloc[tr],
                    test_y[tr],
                    columns,
                    trees,
                    weight,
                    depth,
                )
                oof[va] = model.predict(test_x.iloc[va][columns])
            forward_model = fit(
                train_x,
                train_y,
                test_x.iloc[early],
                test_y[early],
                columns,
                trees,
                weight,
                depth,
            )
            forward = forward_model.predict(test_x.iloc[late][columns])
            for alpha in (0.25, 0.5, 0.75, 1.0):
                group = (1 - alpha) * winner_group + alpha * oof
                time = (1 - alpha) * winner_time + alpha * forward
                group_mae = mae(test_y, group)
                time_mae = mae(test_y[late], time)
                record = {
                    "feature_set": name,
                    "trees": trees,
                    "test_weight": weight,
                    "depth": depth,
                    "alpha": alpha,
                    "group_mae": group_mae,
                    "time_mae": time_mae,
                    "selection_mae": (group_mae + time_mae) / 2,
                }
                experiments.append(record)
            print(
                json.dumps(min(experiments[-4:], key=lambda r: r["selection_mae"])),
                flush=True,
            )
    best = min(experiments, key=lambda r: r["selection_mae"])
    improved = (
        best["selection_mae"] < baseline["selection_mae"] - 0.5
        and best["group_mae"] < baseline["group_mae"]
        and best["time_mae"] < baseline["time_mae"]
    )
    report = {
        "reference_score": 0.77575,
        "reference": baseline,
        "selected": best,
        "improved": improved,
        "experiments": experiments,
        "validation": "Four held-out labeled test vehicle folds and purged later time window, same as previous winning candidate",
        "limitations": [
            "The labeled test set has been used for model selection in both versions",
            "Actual improvement over score 0.77575 requires platform submission",
            "Offline route features are unavailable in the current production request",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    if not improved:
        print(
            json.dumps({"reference": baseline, "selected": best, "improved": False}),
            flush=True,
        )
        return
    columns = sets[best["feature_set"]]
    final = fit(
        train_x,
        train_y,
        test_x,
        test_y,
        columns,
        best["trees"],
        best["test_weight"],
        best["depth"],
    )
    final.save_model(str(output / "delay.cbm"))
    (output / "metadata.json").write_text(
        json.dumps(
            {
                "features": columns,
                "feature_version": "v1",
                "blend_with_winner": best["alpha"],
                "config": best,
                "model_version": "legacy-score-anchored-v3",
                "offline_only": True,
            },
            indent=2,
        )
    )
    winner_submission = pd.read_csv(winner / "submission.csv", sep=";")
    fresh = pd.DataFrame(
        {"sample_id": val_p.sample_id, "prediction": final.predict(val_x[columns])}
    )
    joined = winner_submission.merge(
        fresh, on="sample_id", suffixes=("_winner", "_new"), validate="one_to_one"
    )
    joined["prediction"] = (1 - best["alpha"]) * joined.prediction_winner + best[
        "alpha"
    ] * joined.prediction_new
    template = pd.read_csv(root / "sample_submission.csv", sep=";")
    if (
        len(joined) != len(template)
        or set(joined.sample_id) != set(template.sample_id)
        or not np.isfinite(joined.prediction).all()
    ):
        raise ValueError("Invalid submission")
    joined.set_index("sample_id").loc[template.sample_id].reset_index()[
        ["sample_id", "prediction"]
    ].to_csv(output / "submission.csv", sep=";", index=False)
    print(
        json.dumps({"reference": baseline, "selected": best, "improved": True}),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT)
    parser.add_argument("--winner", type=Path, default=OUTPUT / "model_1")
    parser.add_argument("--reference", type=Path, default=OUTPUT / "reference-v1")
    parser.add_argument("--output", type=Path, default=OUTPUT / "model_2")
    args = parser.parse_args()
    run(args.dataset, args.winner, args.reference, args.output)
