from datetime import datetime

from commons.pydantic.models import FrozenModel


class RedisTelemetryRecord(FrozenModel):
    timestamp: datetime
    longitude: float
    latitude: float
    speed: float
    course: float
