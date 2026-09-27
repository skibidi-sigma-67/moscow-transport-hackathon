import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from catboost import CatBoostClassifier, CatBoostRegressor

from commons.contracts.v1.ml.responses import MLPredictionResponse
from commons.enums import RiskLevel
from commons.ml_context import prepare_context
from commons.ml_features import FEATURE_VERSION


def timestamp(dt):
    return (dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt).timestamp()


class Predictor:
    def __init__(self, directory):
        directory = Path(directory)
        
        self.meta = json.loads((directory / "metadata.json").read_text())
        if self.meta["feature_version"] != FEATURE_VERSION:
            raise ValueError("Incompatible feature schema")
            
        self.regressor = CatBoostRegressor()
        self.regressor.load_model(str(directory / "delay.cbm"))
        
        self.classifier = CatBoostClassifier()
        self.classifier.load_model(str(directory / "late.cbm"))
        
        self.gps_meta = json.loads((directory / "gps_report.json").read_text())[
            "selected"
        ]
        
        self.gps_regressor = CatBoostRegressor()
        self.gps_regressor.load_model(str(directory / "gps_delay.cbm"))
        
        self.gps_classifier = CatBoostClassifier()
        self.gps_classifier.load_model(str(directory / "gps_late.cbm"))

    def predict(self, request):
        now = timestamp(request.current_time_T)
        
        common = {
            "prediction_time": request.current_time_T,
            "target_time": request.target_time_begin,
            "published_at": datetime.now(UTC),
            "model_version": self.meta["model_version"],
            "telemetry_time_policy": request.telemetry_time_policy,
        }
        
        if not 600 < timestamp(request.target_time_begin) - now <= 900:
            return MLPredictionResponse(status="NO_TARGET", **common)
            
        context = prepare_context(request)
        hint, gps_mode, f = (context.hint, context.gps_mode, context.values)
        
        common.update(
            telemetry_time_policy=request.telemetry_time_policy,
            telemetry_count=context.telemetry_count,
            historical_count=context.historical_count,
            coverage_900=f["coverage_900"],
        )
        
        if gps_mode:
            common["model_version"] += "-gps"
            
        if f["gps_age_s"] > 900 and hint is None:
            return MLPredictionResponse(
                status="UNAVAILABLE", gps_age_s=f["gps_age_s"], **common
            )
            
        meta = self.gps_meta if gps_mode else self.meta
        regressor = self.gps_regressor if gps_mode else self.regressor
        classifier = self.gps_classifier if gps_mode else self.classifier
        
        x = np.array([[f[c] for c in meta["features"]]], dtype=float)
        
        delay = float(regressor.predict(x, thread_count=1)[0])
        if not gps_mode and self.meta["mode"] == "residual":
            delay += hint or 0.0
            
        raw = float(classifier.predict_proba(x, thread_count=1)[0, 1])
        raw = max(1e-06, min(1 - 1e-06, raw))
        
        z = (
            self.meta["calibration_coef"] * math.log(raw / (1 - raw))
            + self.meta["calibration_intercept"]
        )
        probability = raw if gps_mode else 1 / (1 + math.exp(-max(-50, min(50, z))))
        
        degraded = (
            gps_mode
            or f["gps_age_s"] > 60
            or hint is None
            or bool(context.observations)
        )
        
        risk = (
            RiskLevel.RED
            if probability >= self.meta["risk_threshold"]
            else RiskLevel.YELLOW
            if degraded or probability >= self.meta["risk_threshold"] / 2
            else RiskLevel.GREEN
        )
        
        observations = list(context.observations)
        
        if f["gps_age_s"] > 60:
            observations.append("GPS устарел")
            
        if hint is None:
            observations.append("Текущее отклонение неизвестно")
            
        if f["coverage_180"] > 0.5 and f["idle_180"] > 0.5:
            observations.append(
                "Более половины наблюдаемого времени скорость ниже 3 км/ч"
            )
            
        radius = self.gps_meta["radius"] if gps_mode else self.meta["interval_radius_s"]
        
        return MLPredictionResponse(
            predicted_delay_s=delay,
            p_late=probability,
            risk_level=risk,
            status="DEGRADED" if degraded else "OK",
            gps_age_s=f["gps_age_s"],
            interval_low_s=delay - radius,
            interval_high_s=delay + radius,
            observations=observations,
            **common,
        )
