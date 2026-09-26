import json
from dataclasses import dataclass
from pathlib import Path

from commons.contracts.v1.ml.requests import MLPredictionRequest
from commons.contracts.v1.ml.responses import MLPredictionResponse
from commons.enums import IncidentPattern, RiskLevel


@dataclass(frozen=True)
class DelayPredictionModel:
    blend_cur_dev: float
    global_mean: float
    tr_id_means: dict[str, float]

    @classmethod
    def load(cls, path: Path) -> "DelayPredictionModel":
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        return cls(
            blend_cur_dev=float(payload["blend_cur_dev"]),
            global_mean=float(payload["global_mean"]),
            tr_id_means={str(k): float(v) for k, v in payload["tr_id_means"].items()},
        )

    def predict(self, request: MLPredictionRequest) -> MLPredictionResponse:
        historical_mean = self.tr_id_means.get(str(request.tr_id), self.global_mean)
        predicted_delay_s = self._clip(
            self.blend_cur_dev * request.cur_dev_s
            + (1.0 - self.blend_cur_dev) * historical_mean
        )

        return MLPredictionResponse(
            predicted_delay_s=predicted_delay_s,
            risk_level=self._risk_level(predicted_delay_s),
            pattern_reason=self._pattern_reason(predicted_delay_s, request),
        )

    @staticmethod
    def _clip(value: float) -> float:
        return max(-600.0, min(900.0, value))

    @staticmethod
    def _risk_level(predicted_delay_s: float) -> RiskLevel:
        if predicted_delay_s >= 180.0:
            return RiskLevel.RED
        if predicted_delay_s >= 120.0:
            return RiskLevel.YELLOW
        return RiskLevel.GREEN

    @staticmethod
    def _pattern_reason(
        predicted_delay_s: float,
        request: MLPredictionRequest,
    ) -> IncidentPattern | None:
        if predicted_delay_s < 120.0:
            return None

        if request.idle_time_s >= 60.0 or request.segment_avg_speed <= 5.0:
            return IncidentPattern.TRAFFIC_JAM

        recent_speeds = [point.speed for point in request.recent_telemetry[-5:]]
        if recent_speeds and sum(recent_speeds) / len(recent_speeds) <= 5.0:
            return IncidentPattern.TRAFFIC_JAM

        return IncidentPattern.UNKNOWN_DELAY
