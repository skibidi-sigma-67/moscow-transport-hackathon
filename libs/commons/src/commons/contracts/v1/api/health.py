from pydantic import Field

from commons.pydantic.models import FrozenModel


class HealthSettings(FrozenModel):
    prediction_cache_ttl: int
    telemetry_max_history: int
    stop_speed_threshold_kmh: float
    ml_telemetry_window_minutes: int
    max_idle_gap_s: float
    historical_packet_delay_s: float
    dashboard_websocket_update_interval_s: float


class HealthResponse(FrozenModel):
    status: str = Field(..., description="Статус сервиса")
    ml_status: str = Field(..., description="Статус сервиса ML")
    settings: HealthSettings
