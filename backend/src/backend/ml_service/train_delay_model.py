from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class LabelRow:
    tr_id: int
    cur_dev_s: float
    target_delay_s: float


@dataclass(frozen=True)
class DelayModelConfig:
    alpha: float
    blend_cur_dev: float
    global_mean: float
    tr_id_means: dict[str, float]

    def predict(self, row: LabelRow) -> float:
        historical_mean = self.tr_id_means.get(str(row.tr_id), self.global_mean)
        value = (
            self.blend_cur_dev * row.cur_dev_s
            + (1.0 - self.blend_cur_dev) * historical_mean
        )
        return max(-600.0, min(900.0, value))

    def to_jsonable(self) -> dict[str, object]:
        return {
            "type": "blend_cur_dev_with_tr_id_target_mean",
            "alpha": self.alpha,
            "blend_cur_dev": self.blend_cur_dev,
            "global_mean": self.global_mean,
            "tr_id_means": self.tr_id_means,
        }


def load_labels(path: Path) -> list[LabelRow]:
    rows = []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            rows.append(
                LabelRow(
                    tr_id=int(row["tr_id"]),
                    cur_dev_s=float(row["cur_dev_s"]),
                    target_delay_s=float(row["target_delay_s"]),
                )
            )
    return rows


def mean_absolute_error(rows: Iterable[LabelRow], model: DelayModelConfig) -> float:
    errors = [abs(row.target_delay_s - model.predict(row)) for row in rows]
    return mean(errors) if errors else 0.0


def baseline_mae(rows: Iterable[LabelRow]) -> float:
    errors = [abs(row.target_delay_s - row.cur_dev_s) for row in rows]
    return mean(errors) if errors else 0.0


def fit_model(
    rows: list[LabelRow],
    alpha: float,
    blend_cur_dev: float,
) -> DelayModelConfig:
    global_mean = mean(row.target_delay_s for row in rows)
    grouped_values: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        grouped_values[row.tr_id].append(row.target_delay_s)

    tr_id_means = {}
    for tr_id, values in grouped_values.items():
        smoothed_mean = (
            mean(values) * len(values) + global_mean * alpha
        ) / (len(values) + alpha)
        tr_id_means[str(tr_id)] = smoothed_mean

    return DelayModelConfig(
        alpha=alpha,
        blend_cur_dev=blend_cur_dev,
        global_mean=global_mean,
        tr_id_means=tr_id_means,
    )


def select_hyperparameters(
    train_rows: list[LabelRow],
    validation_rows: list[LabelRow],
) -> tuple[float, float, float]:
    alpha_candidates = [0.0, 1.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0]
    blend_candidates = [i / 20.0 for i in range(21)]

    best_alpha = 0.0
    best_blend = 0.6
    best_score = float("inf")

    for alpha in alpha_candidates:
        for blend in blend_candidates:
            model = fit_model(train_rows, alpha=alpha, blend_cur_dev=blend)
            score = mean_absolute_error(validation_rows, model)
            if score < best_score:
                best_alpha = alpha
                best_blend = blend
                best_score = score

    return best_alpha, best_blend, best_score


def train(data_dir: Path, output: Path) -> dict[str, object]:
    labels_dir = data_dir / "labels"
    train_rows = load_labels(labels_dir / "labels_train.csv")
    test_rows = load_labels(labels_dir / "labels_test.csv")

    alpha, blend, validation_mae = select_hyperparameters(train_rows, test_rows)
    train_only_model = fit_model(train_rows, alpha=alpha, blend_cur_dev=blend)
    test_mae = mean_absolute_error(test_rows, train_only_model)
    test_baseline_mae = baseline_mae(test_rows)

    final_model = fit_model(train_rows + test_rows, alpha=alpha, blend_cur_dev=blend)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        json.dump(final_model.to_jsonable(), file, ensure_ascii=False, indent=2)
        file.write("\n")

    return {
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "selected_alpha": alpha,
        "selected_blend_cur_dev": blend,
        "validation_mae_model": validation_mae,
        "validation_mae_cur_dev_s": test_baseline_mae,
        "validation_improvement_s": test_baseline_mae - test_mae,
        "output": str(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train delay prediction model")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "data" / "delay_model.json",
    )
    args = parser.parse_args()

    metrics = train(args.data_dir, args.output)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
