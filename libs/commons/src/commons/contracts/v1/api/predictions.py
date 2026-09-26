from datetime import datetime

from pydantic import Field

from commons.enums import RiskLevel
from commons.pydantic.models import FrozenModel


class PredictionLogDto(FrozenModel):
    id: int = Field(..., description="Уникальный идентификатор записи предсказания")
    tr_id: int = Field(
        ..., description="Уникальный идентификатор транспортного средства"
    )
    predicted_delay_s: float = Field(
        ..., description="Предсказанная задержка в секундах"
    )
    risk_level: RiskLevel = Field(
        ..., description="Уровень риска (Зеленый, Желтый, Красный)"
    )
    pattern_reason: str | None = Field(
        None, description="Причина задержки, если обнаружена ML-моделью (паттерн)"
    )
    created_at: datetime = Field(..., description="Время создания записи предсказания")
