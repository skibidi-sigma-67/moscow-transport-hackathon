from datetime import datetime

from pydantic import Field

from commons.enums import IncidentPattern, RiskLevel
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
    pattern_reason: IncidentPattern | None = Field(
        None, description="Технический код паттерна инцидента (например, 'TRAFFIC_JAM')"
    )
    created_at: datetime = Field(..., description="Время создания записи предсказания")
