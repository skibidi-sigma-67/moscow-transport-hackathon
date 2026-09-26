from datetime import datetime

from pydantic import Field

from commons.pydantic.models import FrozenModel


class TelemetryPoint(FrozenModel):
    timestamp: datetime = Field(..., description="Время фиксации координат")
    longitude: float = Field(..., description="Долгота")
    latitude: float = Field(..., description="Широта")
    speed: float = Field(..., description="Скорость движения в км/ч")
    course: float = Field(..., description="Курс направления")
    location_valid: bool = Field(..., description="Признак валидности координат")
    packet_time: datetime = Field(..., description="Время получения пакета")
    is_historical: bool = Field(..., description="Признак исторической записи (из черного ящика)")


class MLPredictionRequest(FrozenModel):
    tr_id: int = Field(..., description="Идентификатор транспортного средства")
    target_stop_id: int = Field(..., description="Идентификатор целевой остановки")
    target_time_begin: datetime = Field(
        ..., description="Плановое время прибытия по расписанию"
    )
    current_time_T: datetime = Field(..., description="Текущее время T")
    cur_dev_s: float = Field(
        ..., description="Текущее фактическое отклонение от расписания (в секундах)"
    )
    segment_avg_speed: float = Field(
        ..., description="Средняя скорость на текущем сегменте (км/ч)"
    )
    idle_time_s: float = Field(
        ..., description="Время простоя на светофорах/в пробках (в секундах)"
    )
    window_start_time: datetime = Field(..., description="Начало временного окна телеметрии")
    window_end_time: datetime = Field(..., description="Конец временного окна телеметрии")
    coverage_ratio: float = Field(..., description="Отношение фактического кол-ва точек к ожидаемому")
    recent_telemetry: list[TelemetryPoint] = Field(
        ..., description="Последние телеметрические отметки (история)"
    )
