import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from research.data.dataset import OUTPUT, ROOT
from research.legacy_dataset import load
from research.training.legacy_upgrade import mae
from research.training.legacy_upgrade_v3 import fit


def run(root, winner, output):
    root, winner, output = map(Path, (root, winner, output))
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
    winner_meta = json.loads((winner / "metadata.json").read_text())
    base_columns, config = winner_meta["features"], winner_meta["config"]
    folds = list(GroupKFold(4).split(test_x, test_y, test_p.tr_id))
    boundary = float(test_p.now.quantile(0.7))
    early = np.flatnonzero(
        (test_p.now < boundary - 1800)
        & (np.maximum(test_p.target_time, test_p.target_time + test_y) < boundary - 900)
    )
    late = np.flatnonzero(test_p.now >= boundary)
    baseline_oof = np.empty(len(test_p))
    for tr, va in folds:
        model = fit(
            train_x,
            train_y,
            test_x.iloc[tr],
            test_y[tr],
            base_columns,
            config["trees"],
            config["test_weight"],
            config["depth"],
        )
        baseline_oof[va] = model.predict(test_x.iloc[va][base_columns])
    forward_model = fit(
        train_x,
        train_y,
        test_x.iloc[early],
        test_y[early],
        base_columns,
        config["trees"],
        config["test_weight"],
        config["depth"],
    )
    baseline_forward = forward_model.predict(test_x.iloc[late][base_columns])
    vehicle_weights = (
        val_p.tr_id.value_counts(normalize=True)
        .reindex(test_p.tr_id)
        .fillna(0)
        .to_numpy()
        / test_p.tr_id.map(test_p.tr_id.value_counts()).to_numpy()
    )

    def weighted_error(prediction):
        return float(np.average(abs(test_y - prediction), weights=vehicle_weights))

    baseline = {
        "group_mae": mae(test_y, baseline_oof),
        "time_mae": mae(test_y[late], baseline_forward),
        "validate_vehicle_mae": weighted_error(baseline_oof),
    }
    baseline["selection_mae"] = (baseline["group_mae"] + baseline["time_mae"]) / 2
    sets = {
        "base": base_columns,
        "schedule_pace": base_columns + ["required_speed_kmh", "distance_per_stop_m"],
        "current_position": base_columns
        + ["last_lon", "last_lat", "last_speed", "heading_alignment"],
        "relative_position": base_columns
        + ["target_east_m", "target_north_m", "required_speed_kmh"],
        "pace_and_motion": base_columns
        + [
            "required_speed_kmh",
            "distance_per_stop_m",
            "last_speed",
            "heading_alignment",
            "speed_300",
            "idle_300",
        ],
    }
    experiments = []
    for name, columns in sets.items():
        for trees, weight, depth in (
            (120, 4, 5),
            (160, 4, 6),
            (180, 4, 6),
            (160, 8, 6),
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
            forward = fit(
                train_x,
                train_y,
                test_x.iloc[early],
                test_y[early],
                columns,
                trees,
                weight,
                depth,
            ).predict(test_x.iloc[late][columns])
            for alpha in (0.25, 0.5, 0.75, 1.0):
                group = (1 - alpha) * baseline_oof + alpha * oof
                time = (1 - alpha) * baseline_forward + alpha * forward
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
                    "validate_vehicle_mae": weighted_error(group),
                    "selection_mae": (group_mae + time_mae) / 2,
                }
                experiments.append(record)
            print(
                json.dumps(min(experiments[-4:], key=lambda r: r["selection_mae"])),
                flush=True,
            )
    eligible = [
        item
        for item in experiments
        if item["selection_mae"] < baseline["selection_mae"] - 0.5
        and item["group_mae"] < baseline["group_mae"]
        and item["time_mae"] < baseline["time_mae"]
        and item["validate_vehicle_mae"] < baseline["validate_vehicle_mae"]
    ]
    improved = bool(eligible)
    best = min(
        eligible if improved else experiments,
        key=lambda item: (
            0.4 * item["group_mae"]
            + 0.3 * item["time_mae"]
            + 0.3 * item["validate_vehicle_mae"]
        ),
    )
    report = {
        "reference_score": 0.85504,
        "reference": baseline,
        "selected": best,
        "improved": improved,
        "experiments": experiments,
        "validation": "Four held-out labeled-test vehicle folds, a purged later test window, and a test error weighted by validate vehicle frequency. All three must improve; among eligible models choose 0.4 group + 0.3 time + 0.3 vehicle-weighted MAE",
        "limitations": [
            "Repeated selection on labeled test risks overfitting",
            "Real platform score requires submission",
            "Competition route geometry is absent from the current online request",
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
                "feature_version": "v1-plus",
                "blend_with_winner": best["alpha"],
                "config": best,
                "model_version": "legacy-score-anchored-v4",
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
    parser.add_argument("--winner", type=Path, default=OUTPUT / "model_2")
    parser.add_argument("--output", type=Path, default=OUTPUT / "model_3")
    args = parser.parse_args()
    run(args.dataset, args.winner, args.output)
