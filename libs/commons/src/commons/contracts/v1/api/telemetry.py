from datetime import datetime

from pydantic import Field

from commons.pydantic.models import FrozenModel


class TelemetryPointDto(FrozenModel):
    timestamp: datetime = Field(..., description="Временная метка получения координат")
    longitude: float = Field(..., description="Долгота")
    latitude: float = Field(..., description="Широта")
    speed: float = Field(..., description="Скорость в км/ч")
    course: float = Field(..., description="Курс (направление движения в градусах)")
