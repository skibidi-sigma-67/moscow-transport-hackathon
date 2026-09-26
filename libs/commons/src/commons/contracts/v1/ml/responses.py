from pydantic import Field

from commons.enums import RiskLevel
from commons.pydantic.models import FrozenModel


class MLPredictionResponse(FrozenModel):
    predicted_delay_s: float = Field(
        ..., description="Спрогнозированная задержка (в секундах)"
    )
    risk_level: RiskLevel = Field(..., description="Оценка риска (GREEN, YELLOW, RED)")
    pattern_reason: str | None = Field(
        None,
        description="Выявленный ML-моделью паттерн (например, 'Пробка на перекрестке')",
    )
