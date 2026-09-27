import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.model_selection import GroupKFold

from research.data.dataset import OUTPUT, ROOT
from research.legacy_dataset import load

FEATURES = [
    "cur_dev_s",
    "cur_dev_missing",
    "horizon_s",
    "hour_sin",
    "hour_cos",
    "stops_ahead",
]


def make_model(iterations):
    return CatBoostRegressor(
        loss_function="MAE",
        iterations=iterations,
        depth=6,
        learning_rate=0.08,
        l2_leaf_reg=30,
        random_seed=42,
        thread_count=2,
        verbose=False,
        allow_writing_files=False,
    )


def fit(train_x, train_y, extra_x, extra_y, iterations, extra_weight):
    x = pd.concat((train_x[FEATURES], extra_x[FEATURES]), ignore_index=True)
    y = np.concatenate((train_y, extra_y))
    weights = np.concatenate(
        (np.ones(len(train_y)), np.full(len(extra_y), extra_weight))
    )
    model = make_model(iterations)
    model.fit(x, y, sample_weight=weights)
    return model


def mae(y, prediction):
    return float(np.mean(np.abs(y - prediction)))


def run(root, reference, out):
    root, reference, out = Path(root), Path(reference), Path(out)
    if out.exists():
        raise ValueError("Experiment output must be a new directory")
    out.mkdir(parents=True)
    train_p, train_x, _, _ = load(root, "train")
    real = train_p.tr_id < 1000000
    train_p, train_x = (
        train_p[real].reset_index(drop=True),
        train_x[real].reset_index(drop=True),
    )
    test_p, test_x, _, _ = load(root, "test")
    val_p, val_x, _, _ = load(root, "validate")
    y_train, y_test = (
        train_p.target_delay_s.to_numpy(),
        test_p.target_delay_s.to_numpy(),
    )
    ref_model = CatBoostRegressor()
    ref_model.load_model(str(reference / "delay.cbm"))
    ref_test = ref_model.predict(test_x[FEATURES])
    assert (
        np.max(
            abs(
                ref_test
                - pd.read_csv(reference / "test_predictions.csv").prediction.to_numpy()
            )
        )
        < 1e-9
    )
    folds = list(GroupKFold(4).split(test_x, y_test, test_p.tr_id))
    boundary = float(test_p.now.quantile(0.7))
    forward_train = np.flatnonzero(
        (test_p.now < boundary - 1800)
        & (np.maximum(test_p.target_time, test_p.target_time + y_test) < boundary - 900)
    )
    forward_val = np.flatnonzero(test_p.now >= boundary)
    if not len(forward_train) or not len(forward_val):
        raise ValueError("Empty forward validation")
    experiments = []
    oof_predictions = []
    for trees in (60, 90, 120):
        for weight in (1.0, 2.0, 4.0):
            oof = np.full(len(test_p), np.nan)
            for tr, va in folds:
                model = fit(
                    train_x, y_train, test_x.iloc[tr], y_test[tr], trees, weight
                )
                oof[va] = model.predict(test_x.iloc[va][FEATURES])
            forward = fit(
                train_x,
                y_train,
                test_x.iloc[forward_train],
                y_test[forward_train],
                trees,
                weight,
            ).predict(test_x.iloc[forward_val][FEATURES])
            for blend in (0.25, 0.5, 0.75, 1.0):
                group_pred = (1 - blend) * ref_test + blend * oof
                time_pred = (1 - blend) * ref_test[forward_val] + blend * forward
                group_mae = mae(y_test, group_pred)
                time_mae = mae(y_test[forward_val], time_pred)
                score = (group_mae + time_mae) / 2
                record = {
                    "trees": trees,
                    "test_weight": weight,
                    "blend": blend,
                    "group_mae": group_mae,
                    "time_mae": time_mae,
                    "selection_mae": score,
                }
                experiments.append(record)
                oof_predictions.append(group_pred)
                print(json.dumps(record), flush=True)
    baseline = {
        "group_mae": mae(y_test, ref_test),
        "time_mae": mae(y_test[forward_val], ref_test[forward_val]),
    }
    baseline["selection_mae"] = (baseline["group_mae"] + baseline["time_mae"]) / 2
    index = min(range(len(experiments)), key=lambda i: experiments[i]["selection_mae"])
    best = experiments[index]
    improved = (
        best["selection_mae"] < baseline["selection_mae"] - 0.5
        and best["group_mae"] < baseline["group_mae"]
        and best["time_mae"] < baseline["time_mae"]
    )
    report = {
        "reference": baseline,
        "selected": best,
        "improved": improved,
        "experiments": experiments,
        "validation": "Four held-out groups of labeled test vehicles and a purged forward test window. Reference model was trained only on train.",
        "limitations": [
            "The labeled test split has now been used for model selection and final training",
            "Train and test overlap in vehicles and day",
            "Hidden validate score cannot be calculated locally",
            "This is an offline competition model; current production request lacks planned stops",
        ],
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    pd.DataFrame(
        {
            "sample_id": test_p.sample_id,
            "target": y_test,
            "reference": ref_test,
            "candidate": oof_predictions[index],
        }
    ).to_csv(out / "test_oof.csv", index=False)
    if not improved:
        print("No defensible improvement over the reference", flush=True)
        return
    final = fit(train_x, y_train, test_x, y_test, best["trees"], best["test_weight"])
    final.save_model(str(out / "delay.cbm"))
    (out / "metadata.json").write_text(
        json.dumps(
            {
                "feature_version": "v1",
                "features": FEATURES,
                "mode": "direct",
                "config": {
                    "depth": 6,
                    "learning_rate": 0.08,
                    "l2_leaf_reg": 30,
                    "iterations": best["trees"],
                    "test_weight": best["test_weight"],
                },
                "blend": best["blend"],
                "model_version": "legacy-score-anchored-v2",
                "reference": str(reference),
            },
            indent=2,
        )
    )
    reference_submission = pd.read_csv(reference / "submission.csv", sep=";")
    raw = final.predict(val_x[FEATURES])
    candidate = pd.DataFrame({"sample_id": val_p.sample_id, "prediction": raw})
    merged = reference_submission.merge(
        candidate,
        on="sample_id",
        suffixes=("_reference", "_candidate"),
        validate="one_to_one",
    )
    merged["prediction"] = (1 - best["blend"]) * merged.prediction_reference + best[
        "blend"
    ] * merged.prediction_candidate
    template = pd.read_csv(root / "sample_submission.csv", sep=";")
    if (
        len(merged) != len(template)
        or not np.isfinite(merged.prediction).all()
        or set(merged.sample_id) != set(template.sample_id)
    ):
        raise ValueError("Invalid submission")
    merged.set_index("sample_id").loc[template.sample_id].reset_index()[
        ["sample_id", "prediction"]
    ].to_csv(out / "submission.csv", sep=";", index=False)
    print(
        json.dumps({"reference": baseline, "selected": best, "improved": improved}),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT)
    parser.add_argument("--reference", type=Path, default=OUTPUT / "reference-v1")
    parser.add_argument("--output", type=Path, default=OUTPUT / "model_1")
    args = parser.parse_args()
    run(args.dataset, args.reference, args.output)
