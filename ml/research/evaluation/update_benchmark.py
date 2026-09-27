import argparse
import json
from pathlib import Path

from ml.features import FEATURE_VERSION

from research.data.dataset import OUTPUT, ROOT, export
from research.training.online_train import update
from research.training.train import fit


def run(root, directory, out):
    out = Path(out)
    if out.exists():
        raise ValueError("Use a new experiment directory")
    out.mkdir(parents=True)
    data = export(root, "train", out / "features.csv", policy="receive")
    data = data[data.vehicle.astype(int) < 1000000]
    first, second = data.now.quantile([0.5, 0.8]).tolist()
    initial = data[(data.now < first - 1800) & (data.available_at < first - 900)]
    batch = data[
        (data.now >= first)
        & (data.now < second - 1800)
        & (data.available_at < second - 900)
    ]
    valid = data[data.now >= second]
    meta = json.loads((Path(directory) / "metadata.json").read_text())
    cols, mode = meta["features"], meta["mode"]
    m = fit(meta["config"], initial[cols], initial.target_delay_s.to_numpy(), mode)
    parent = out / "parent"
    parent.mkdir()
    m.save_model(str(parent / "delay.cbm"))
    meta.update(
        feature_version=FEATURE_VERSION,
        training_sample_ids=initial.sample_id.tolist(),
        training_rows=len(initial),
        training_max_time=float(initial.now.max()),
        training_labels_available_at=float(initial.available_at.max()),
        iterations=m.tree_count_,
    )
    (parent / "metadata.json").write_text(json.dumps(meta, indent=2))
    batch.to_csv(out / "batch.csv", index=False)
    valid.to_csv(out / "validation.csv", index=False)
    initial.to_csv(out / "replay.csv", index=False)
    result = update(
        parent,
        out / "batch.csv",
        out / "validation.csv",
        out / "candidate",
        out / "replay.csv",
    )
    try:
        update(parent, out / "batch.csv", out / "batch.csv", out / "overlap")
    except ValueError as exc:
        result["overlap_rejected"] = str(exc)
    else:
        raise AssertionError("Overlapping validation accepted")
    result["scope"] = (
        "Historical forward replay on one day; not a production update speed guarantee"
    )
    (out / "benchmark.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT)
    parser.add_argument("--model", type=Path, default=OUTPUT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.model, args.output), indent=2))
