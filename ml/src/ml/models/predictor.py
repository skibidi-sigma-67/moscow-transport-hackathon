import json
from pathlib import Path

import numpy as np
from catboost import CatBoostRegressor

from commons.contracts.v1.ml.responses import MLPredictionResponse
from commons.enums import RiskLevel
from ml.features import FEATURE_VERSION, features


class Predictor:
    def __init__(self, directory):
        directory = Path(directory)
        self.meta = json.loads((directory / "metadata.json").read_text())
        if self.meta["feature_version"] not in (4, FEATURE_VERSION):
            raise ValueError("Incompatible feature schema")
        self.regressor = CatBoostRegressor()
        self.regressor.load_model(str(directory / "delay.cbm"))
        if self.regressor.feature_names_ != self.meta["features"]:
            raise ValueError("Incompatible model features")

    def predict(self, request):
        values = features(request, self.meta["features"])
        x = np.array([[values[c] for c in self.meta["features"]]], dtype=object)
        delay = float(self.regressor.predict(x, thread_count=1)[0])
        if self.meta["mode"] == "residual":
            delay += request.cur_dev_s
        if not np.isfinite(delay):
            raise ValueError("Non-finite prediction")
        risk = (
            RiskLevel.RED
            if delay > 300
            else RiskLevel.YELLOW
            if delay > 120
            else RiskLevel.GREEN
        )
        return MLPredictionResponse(
            predicted_delay_s=delay, risk_level=risk, pattern_reason=None
        )
