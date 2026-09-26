from datetime import datetime

from pydantic import Field

from commons.pydantic.models import FrozenModel


class SchedulePlanDto(FrozenModel):
    id: int = Field(..., description="Уникальный идентификатор записи расписания")
    tr_id: int = Field(..., description="Идентификатор транспортного средства")
    stop_id: int = Field(..., description="Идентификатор остановки по маршруту")
    time_begin: datetime = Field(
        ..., description="Плановое время прибытия на остановку"
    )
    address: str | None = Field(None, description="Адрес остановки")
    longitude: float | None = Field(None, description="Долгота остановки")
    latitude: float | None = Field(None, description="Широта остановки")
