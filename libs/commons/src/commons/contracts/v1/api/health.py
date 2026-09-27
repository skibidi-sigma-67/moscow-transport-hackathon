from pydantic import Field

from commons.pydantic.models import FrozenModel


class HealthSettings(FrozenModel):
    prediction_cache_ttl: int = Field(
        ..., description="Время жизни кэша предиктов в секундах"
    )
    telemetry_max_history: int = Field(
        ..., description="Максимальное количество исторических записей телеметрии"
    )
    stop_speed_threshold_kmh: float = Field(
        ..., description="Порог скорости для фиксации остановки (км/ч)"
    )
    ml_telemetry_window_minutes: int = Field(
        ..., description="Окно агрегации телеметрии для ML-модели (в минутах)"
    )
    max_idle_gap_s: float = Field(
        ..., description="Максимально допустимый разрыв для простоя (в секундах)"
    )
    historical_packet_delay_s: float = Field(
        ..., description="Искусственная задержка для исторических пакетов (в секундах)"
    )
    dashboard_websocket_update_interval_s: float = Field(
        ..., description="Интервал обновления дашборда по WebSocket (в секундах)"
    )


class HealthResponse(FrozenModel):
    status: str = Field(..., description="Статус сервиса")
    ml_status: str = Field(..., description="Статус сервиса ML")
    settings: HealthSettings = Field(..., description="Текущие настройки приложения")
