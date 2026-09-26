from datetime import datetime

from commons.pydantic.models import FrozenModel


class RedisTelemetryRecord(FrozenModel):
    timestamp: datetime
    longitude: float
    latitude: float
    speed: float
    course: float
    location_valid: bool = True
    packet_time: datetime | None = None
    is_historical: bool = False
