import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from ml.models.predictor import ENSEMBLE_FILES, Predictor
from research.data.dataset import OUTPUT

APPROVED_MODELS = {
    "legacy-upgrade-v3": (
        "994e95749d4d1efbf9e8e0acca77a4b5696bfa933d08f653dbf276922ba6060b"
    ),
    "legacy-upgrade-v4b": (
        "5d663592fb4387dabc79890c7950b28879f27fe391b53cf303abd2787299471d"
    ),
    "legacy-upgrade-v5": (
        "abf81c67a48b92611fcad3f0d476826c0d26d7764c674fb7bf879bd47f43b3a9"
    ),
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def package(source, schedule, output):
    source, schedule, output = map(Path, (source, schedule, output))
    if output.exists():
        raise ValueError("Output must be a new deployment directory")
    for name, expected in APPROVED_MODELS.items():
        if sha256(source / name / "delay.cbm") != expected:
            raise ValueError(f"Unapproved model: {name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}-", dir=output.parent
    ) as temporary:
        bundle = Path(temporary)
        for relative in ENSEMBLE_FILES:
            origin = schedule if relative == "schedule_plan.csv" else source / relative
            destination = bundle / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, destination)
        manifest = {
            "strategy": "schedule_ensemble_v1",
            "reference_submission_score": 0.90679,
            "sha256": {
                relative: sha256(bundle / relative)
                for relative in sorted(ENSEMBLE_FILES)
            },
        }
        (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2))
        Predictor(bundle, "schedule_ensemble")
        bundle.chmod(0o755)
        bundle.rename(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, default=OUTPUT)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(package(args.models, args.schedule, args.output))
