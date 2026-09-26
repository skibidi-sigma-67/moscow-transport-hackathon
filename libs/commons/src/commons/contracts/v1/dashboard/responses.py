from datetime import datetime

from pydantic import Field

from commons.enums import RiskLevel
from commons.pydantic.models import FrozenModel


class IncidentCard(FrozenModel):
    has_incident: bool = Field(..., description="Наличие инцидента/отклонения от нормы")
    predicted_delay_s: float | None = Field(
        None, description="Предсказанная задержка в секундах, если есть инцидент"
    )
    reason: str | None = Field(
        None,
        description="Текстовое описание причины инцидента или обнаруженного паттерна",
    )
    route_segment: str | None = Field(
        None, description="Участок маршрута, где прогнозируется задержка"
    )


class VehicleState(FrozenModel):
    tr_id: int = Field(..., description="Идентификатор транспортного средства")
    longitude: float = Field(..., description="Текущая долгота")
    latitude: float = Field(..., description="Текущая широта")
    risk_color: RiskLevel = Field(
        ..., description="Текущий уровень риска (цвет светофора)"
    )
    incident_card: IncidentCard | None = Field(
        None,
        description="Карточка инцидента (присутствует, если риск отличается от зеленого)",
    )


class DashboardStateResponse(FrozenModel):
    timestamp: datetime = Field(
        ..., description="Временная метка формирования состояния дашборда"
    )
    vehicles: list[VehicleState] = Field(
        ..., description="Список активных транспортных средств и их состояние"
    )
