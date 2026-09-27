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
    is_historical: bool = Field(
        ..., description="Признак исторической записи (из черного ящика)"
    )


class RouteFeatures(FrozenModel):
    cur_dev_missing: float = Field(
        ..., description="Признак отсутствия исторического отклонения"
    )
    horizon_s: float = Field(
        ...,
        description="Горизонт предсказания в секундах (разница между плановым прибытием и текущим временем)",
    )
    hour_sin: float = Field(
        ..., description="Синус текущего времени суток (для учета цикличности)"
    )
    hour_cos: float = Field(
        ..., description="Косинус текущего времени суток (для учета цикличности)"
    )
    stops_ahead: float = Field(
        ..., description="Количество остановок до целевой остановки"
    )
    target_lon: float = Field(..., description="Долгота целевой остановки")
    target_lat: float = Field(..., description="Широта целевой остановки")
    distance_target_m: float = Field(
        ..., description="Дистанция до целевой остановки по прямой (в метрах)"
    )
    gps_age_s: float = Field(
        ..., description="Возраст последней валидной GPS-отметки в секундах"
    )
    last_lon: float = Field(..., description="Долгота из последней валидной отметки")
    last_lat: float = Field(..., description="Широта из последней валидной отметки")
    last_speed: float = Field(..., description="Скорость из последней валидной отметки")
    heading_alignment: float = Field(
        ...,
        description="Согласованность текущего курса и направления на цель (косинус разницы углов)",
    )
    target_east_m: float = Field(
        ..., description="Смещение до цели по оси Восток (в метрах)"
    )
    target_north_m: float = Field(
        ..., description="Смещение до цели по оси Север (в метрах)"
    )


class TelemetryAggregates(FrozenModel):
    segment_avg_speed: float = Field(
        ..., description="Средняя скорость на текущем сегменте (км/ч)"
    )
    idle_time_s: float = Field(
        ..., description="Время простоя на светофорах/в пробках (в секундах)"
    )
    coverage_ratio: float = Field(
        ..., description="Отношение фактического кол-ва точек к ожидаемому"
    )


class TelemetryWindow(FrozenModel):
    start_time: datetime = Field(..., description="Начало временного окна телеметрии")
    end_time: datetime = Field(..., description="Конец временного окна телеметрии")
    recent_points: list[TelemetryPoint] = Field(
        ..., description="Последние телеметрические отметки (история)"
    )


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
    aggregates: TelemetryAggregates = Field(
        ..., description="Агрегированные показатели"
    )
    window: TelemetryWindow = Field(..., description="Окно телеметрии и точки")
    route_features: RouteFeatures | None = Field(
        default=None, description="Прекомпилированные фичи маршрута (из расписания)"
    )
