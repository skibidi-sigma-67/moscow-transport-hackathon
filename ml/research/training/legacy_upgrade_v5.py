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


def run(root, winner, previous, output, report_path):
    root, winner, previous, output, report_path = map(
        Path, (root, winner, previous, output, report_path)
    )
    if output.exists():
        raise ValueError("Output must be a new candidate directory")
    train_p, train_x, _, _ = load(root, "train")
    real = train_p.tr_id < 1000000
    train_p, train_x = (
        train_p[real].reset_index(drop=True),
        train_x[real].reset_index(drop=True),
    )
    test_p, test_x, _, _ = load(root, "test")
    validate_p, validate_x, _, _ = load(root, "validate")
    train_y = train_p.target_delay_s.to_numpy()
    test_y = test_p.target_delay_s.to_numpy()
    folds = list(GroupKFold(4).split(test_x, test_y, test_p.tr_id))
    boundary = float(test_p.now.quantile(0.7))
    early = np.flatnonzero(
        (test_p.now < boundary - 1800)
        & (np.maximum(test_p.target_time, test_p.target_time + test_y) < boundary - 900)
    )
    late = np.flatnonzero(test_p.now >= boundary)
    counts = test_p.tr_id.value_counts()
    weights = (
        validate_p.tr_id.value_counts(normalize=True)
        .reindex(test_p.tr_id)
        .fillna(0)
        .to_numpy()
        / test_p.tr_id.map(counts).to_numpy()
    )

    def evaluate(columns, trees, depth):
        group = np.empty(len(test_p))
        for training, validation in folds:
            fitted = fit(
                train_x,
                train_y,
                test_x.iloc[training],
                test_y[training],
                columns,
                trees,
                4,
                depth,
            )
            group[validation] = fitted.predict(test_x.iloc[validation][columns])
        forward = fit(
            train_x,
            train_y,
            test_x.iloc[early],
            test_y[early],
            columns,
            trees,
            4,
            depth,
        ).predict(test_x.iloc[late][columns])
        return group, forward

    previous_meta = json.loads((previous / "metadata.json").read_text())
    winner_meta = json.loads((winner / "metadata.json").read_text())
    previous_config = previous_meta["config"]
    winner_config = winner_meta["config"]
    previous_group, previous_time = evaluate(
        previous_meta["features"],
        previous_config["trees"],
        previous_config["depth"],
    )
    winner_group, winner_time = evaluate(
        winner_meta["features"],
        winner_config["trees"],
        winner_config["depth"],
    )
    weight = winner_meta["blend_with_winner"]
    baseline_group = (1 - weight) * previous_group + weight * winner_group
    baseline_time = (1 - weight) * previous_time + weight * winner_time

    def metrics(group, forward):
        return {
            "group_mae": mae(test_y, group),
            "time_mae": mae(test_y[late], forward),
            "validate_vehicle_mae": float(
                np.average(abs(test_y - group), weights=weights)
            ),
        }

    baseline = metrics(baseline_group, baseline_time)
    reference = winner_config
    for key in baseline:
        if abs(baseline[key] - reference[key]) > 1e-6:
            raise ValueError(f"Cannot reproduce winner validation: {key}")

    position = winner_meta["features"]
    sets = {
        "position_pace": position + ["required_speed_kmh", "distance_per_stop_m"],
        "position_trend": position
        + ["speed_300", "idle_300", "trend_300", "coverage_300"],
        "position_pace_trend": position
        + [
            "required_speed_kmh",
            "distance_per_stop_m",
            "speed_300",
            "idle_300",
            "trend_300",
            "coverage_300",
        ],
        "position_vector": position + ["target_east_m", "target_north_m"],
    }
    experiments = []
    for name, columns in sets.items():
        tree_counts = (160, 180, 220) if name == "position_vector" else (180,)
        for trees in tree_counts:
            group, forward = evaluate(columns, trees, 6)
            for alpha in (0.2, 0.35, 0.5):
                blended_group = (1 - alpha) * baseline_group + alpha * group
                blended_time = (1 - alpha) * baseline_time + alpha * forward
                experiments.append(
                    {
                        "feature_set": name,
                        "trees": trees,
                        "alpha": alpha,
                        **metrics(blended_group, blended_time),
                    }
                )
    eligible = [
        item
        for item in experiments
        if item["group_mae"] <= baseline["group_mae"] - 0.5
        and item["time_mae"] <= baseline["time_mae"] - 0.5
        and item["validate_vehicle_mae"] < baseline["validate_vehicle_mae"]
    ]
    best = min(
        eligible or experiments,
        key=lambda item: (
            0.4 * item["group_mae"]
            + 0.3 * item["time_mae"]
            + 0.3 * item["validate_vehicle_mae"]
        ),
    )
    report = {
        "reference_platform_score": 0.89826,
        "reference": baseline,
        "selected": best,
        "improved": bool(eligible),
        "experiments": experiments,
        "validation": "Four held-out vehicle folds and purged later window on labeled test; group and time MAE must improve by at least 0.5 seconds and validate-weighted MAE must improve",
        "limitations": [
            "Labeled test was previously used for model selection",
            "Hidden platform score cannot be estimated from local MAE",
            "Validate vehicle frequencies are used for weighting, but validate labels are unavailable",
            "Test and validate share traffic, so local selection may be optimistic",
            "Route geometry is unavailable to the live HTTP predictor",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False))
    if not eligible:
        print(json.dumps({"reference": baseline, "selected": best, "improved": False}))
        return

    columns = sets[best["feature_set"]]
    final = fit(train_x, train_y, test_x, test_y, columns, best["trees"], 4, 6)
    output.mkdir(parents=True)
    final.save_model(str(output / "delay.cbm"))
    (output / "metadata.json").write_text(
        json.dumps(
            {
                "features": columns,
                "feature_version": "v1-plus",
                "blend_with_winner": best["alpha"],
                "config": best,
                "model_version": "legacy-score-anchored-v5",
                "offline_only": True,
            },
            indent=2,
        )
    )
    winner_submission = pd.read_csv(winner / "submission.csv", sep=";")
    fresh = pd.DataFrame(
        {
            "sample_id": validate_p.sample_id,
            "prediction": final.predict(validate_x[columns]),
        }
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
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({"reference": baseline, "selected": best, "improved": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT)
    parser.add_argument("--winner", type=Path, default=OUTPUT / "legacy-upgrade-v4b")
    parser.add_argument("--previous", type=Path, default=OUTPUT / "legacy-upgrade-v3")
    parser.add_argument("--output", type=Path, default=OUTPUT / "legacy-upgrade-v5")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "reports/v5.json",
    )
    args = parser.parse_args()
    run(args.dataset, args.winner, args.previous, args.output, args.report)
