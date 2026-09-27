import hashlib
import json
from pathlib import Path

import numpy as np
from catboost import CatBoostRegressor

from commons.contracts.v1.ml.responses import MLPredictionResponse
from commons.enums import PredictionStatus, RiskLevel
from ml.features import FEATURE_VERSION, SUPPORTED_FEATURES, features, timestamp
from ml.schedule import ROUTE_FEATURES, ScheduleCatalog, schedule_features

FRESHNESS_SECONDS = 30
ENSEMBLE_WEIGHTS = {
    "legacy-upgrade-v3": 0.4,
    "legacy-upgrade-v4b": 0.4,
    "legacy-upgrade-v5": 0.2,
}
ENSEMBLE_FILES = {
    "delay.cbm",
    "metadata.json",
    "schedule_plan.csv",
} | {
    f"{name}/{filename}"
    for name in ENSEMBLE_WEIGHTS
    for filename in ("delay.cbm", "metadata.json")
}


class Predictor:
    def __init__(self, directory, strategy="baseline"):
        directory = Path(directory)
        if strategy not in ("baseline", "schedule_ensemble"):
            raise ValueError("Unknown prediction strategy")
        required = ["metadata.json", "delay.cbm"]
        if strategy == "schedule_ensemble":
            required.append("manifest.json")
        missing = [name for name in required if not (directory / name).is_file()]
        if missing:
            raise FileNotFoundError(f"Missing model files in {directory}: {missing}")
        self.meta = json.loads((directory / "metadata.json").read_text())
        if self.meta["feature_version"] != FEATURE_VERSION:
            raise ValueError("Incompatible feature schema")
        if not set(self.meta["features"]).issubset(SUPPORTED_FEATURES):
            raise ValueError("Unsupported model features")
        if self.meta.get("offline_only") or self.meta["mode"] not in (
            "direct",
            "residual",
        ):
            raise ValueError("Incompatible model purpose or mode")
        self.regressor = CatBoostRegressor()
        self.regressor.load_model(str(directory / "delay.cbm"))
        if self.regressor.feature_names_ != self.meta["features"]:
            raise ValueError("Incompatible model features")
        self.catalog = None
        self.ensemble = ()
        self.model_version = self.meta["model_version"]
        if strategy == "schedule_ensemble":
            manifest = json.loads((directory / "manifest.json").read_text())
            if (
                manifest.get("strategy") != "schedule_ensemble_v1"
                or set(manifest.get("sha256", {})) != ENSEMBLE_FILES
            ):
                raise ValueError("Incompatible deployment manifest")
            for relative, expected in manifest["sha256"].items():
                digest = hashlib.sha256((directory / relative).read_bytes()).hexdigest()
                if digest != expected:
                    raise ValueError(f"Deployment file checksum mismatch: {relative}")
            self.catalog = ScheduleCatalog(directory / "schedule_plan.csv")
            components = []
            for name, weight in ENSEMBLE_WEIGHTS.items():
                metadata = json.loads((directory / name / "metadata.json").read_text())
                columns = metadata["features"]
                if not metadata.get("offline_only") or not set(columns).issubset(
                    ROUTE_FEATURES
                ):
                    raise ValueError(f"Incompatible ensemble component: {name}")
                model = CatBoostRegressor()
                model.load_model(str(directory / name / "delay.cbm"))
                if model.feature_names_ != columns:
                    raise ValueError(f"Incompatible ensemble features: {name}")
                components.append((model, columns, weight))
            self.ensemble = tuple(components)
            self.model_version = "legacy-score-anchored-v5"

    def _baseline_delay(self, request, values):
        x = np.array([[values[c] for c in self.meta["features"]]], dtype=object)
        delay = float(self.regressor.predict(x, thread_count=1)[0])
        if self.meta["mode"] == "residual":
            delay += request.cur_dev_s
        return delay

    def predict(self, request):
        values = features(request, self.meta["features"])
        matched = None if self.catalog is None else self.catalog.resolve(request)
        if matched is None:
            delay = self._baseline_delay(request, values)
        else:
            route_values = schedule_features(request, *matched)
            delay = sum(
                weight
                * float(
                    model.predict(
                        np.array([[route_values[c] for c in columns]], dtype=float),
                        thread_count=1,
                    )[0]
                )
                for model, columns, weight in self.ensemble
            )
            if not np.isfinite(delay):
                delay = self._baseline_delay(request, values)
                matched = None
        if not np.isfinite(delay):
            raise ValueError("Non-finite prediction")
        risk = (
            RiskLevel.RED
            if delay > 300
            else RiskLevel.YELLOW
            if delay > 120
            else RiskLevel.GREEN
        )
        now = timestamp(request.current_time_T)
        latest = now - values["gps_age_s"]
        live = values["gps_age_s"] <= FRESHNESS_SECONDS and any(
            not point.is_historical
            and point.location_valid
            and timestamp(point.timestamp) == latest
            and timestamp(point.packet_time) <= now
            for point in request.recent_telemetry
        )
        return MLPredictionResponse(
            predicted_delay_s=delay,
            risk_level=risk,
            pattern_reason=None,
            status=PredictionStatus.OK
            if live and (self.catalog is None or matched is not None)
            else PredictionStatus.DEGRADED,
        )
