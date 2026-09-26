from datetime import datetime

from pydantic import Field

from commons.pydantic.models import FrozenModel


class TelemetryPointDto(FrozenModel):
    timestamp: datetime = Field(..., description="Временная метка получения координат")
    longitude: float = Field(..., description="Долгота")
    latitude: float = Field(..., description="Широта")
    speed: float = Field(..., description="Скорость в км/ч")
    course: float = Field(..., description="Курс (направление движения в градусах)")
    location_valid: bool = Field(True, description="Признак валидности координат")
    packet_time: datetime | None = Field(None, description="Время получения пакета")
    is_historical: bool = Field(False, description="Признак исторической записи (из черного ящика)")
