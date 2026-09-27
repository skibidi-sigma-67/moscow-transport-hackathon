import hashlib
import json
from pathlib import Path

import numpy as np
from catboost import CatBoostRegressor

from commons.contracts.v1.ml.requests import RouteFeatures
from commons.contracts.v1.ml.responses import MLPredictionResponse
from commons.enums import IncidentPattern, PredictionStatus, RiskLevel
from ml.features import FEATURE_VERSION, SUPPORTED_FEATURES, features, timestamp

FRESHNESS_SECONDS = 30
ENSEMBLE_WEIGHTS = {
    "model_2": 0.4,
    "model_3": 0.4,
    "model_4": 0.2,
}
ENSEMBLE_FILES = {
    "delay.cbm",
    "metadata.json",
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
        self.feature_names = set(self.meta["features"]) | {
            "speed_mean_180",
            "idle_180",
            "coverage_180",
        }
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
            components = []
            for name, weight in ENSEMBLE_WEIGHTS.items():
                metadata = json.loads((directory / name / "metadata.json").read_text())
                columns = metadata["features"]
                if not metadata.get("offline_only") or not set(columns).issubset(
                    set(RouteFeatures.model_fields.keys())
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
        values = features(request, self.feature_names)
        if request.route_features is None:
            delay = self._baseline_delay(request, values)
            matched = False
        else:
            route_values = request.route_features.model_dump()
            route_values["cur_dev_s"] = request.cur_dev_s
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
            matched = True
            if not np.isfinite(delay):
                delay = self._baseline_delay(request, values)
                matched = False
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
            for point in request.window.recent_points
        )
        pattern = None
        if risk != RiskLevel.GREEN:
            pattern = IncidentPattern.UNKNOWN_DELAY
            if (
                live
                and values["coverage_180"] >= 0.5
                and values["speed_mean_180"] <= 8
                and values["idle_180"] >= 0.5
            ):
                pattern = IncidentPattern.TRAFFIC_JAM
        return MLPredictionResponse(
            predicted_delay_s=delay,
            risk_level=risk,
            pattern_reason=pattern,
            status=PredictionStatus.OK
            if live and (not self.ensemble or matched)
            else PredictionStatus.DEGRADED,
        )
