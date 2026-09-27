from pydantic import Field

from commons.enums import IncidentPattern, PredictionStatus, RiskLevel
from commons.pydantic.models import FrozenModel


class MLPredictionResponse(FrozenModel):
    predicted_delay_s: float = Field(
        ..., description="Спрогнозированная задержка (в секундах)"
    )
    risk_level: RiskLevel = Field(..., description="Оценка риска (GREEN, YELLOW, RED)")
    pattern_reason: IncidentPattern | None = Field(
        None,
        description="Технический код паттерна инцидента (например, 'TRAFFIC_JAM')",
    )
    status: PredictionStatus = Field(
        PredictionStatus.OK, description="Статус предсказания"
    )
