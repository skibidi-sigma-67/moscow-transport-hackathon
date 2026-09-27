import math
from bisect import bisect_right
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from geopy.distance import distance as geopy_distance

from backend.modules.ml.service import MLService
from backend.modules.schedule.service import ScheduleService
from backend.modules.telemetry.service import TelemetryService
from backend.settings import Settings
from commons.contracts.v1.api.predictions import PredictionLogDto
from commons.contracts.v1.ml.requests import (
    MLPredictionRequest,
    RouteFeatures,
    TelemetryAggregates,
    TelemetryPoint,
    TelemetryWindow,
)
from commons.enums import IncidentPattern, RiskLevel

from .repository import PredictionRepository


class PredictionService:
    def __init__(
        self,
        repository: PredictionRepository,
        telemetry_service: TelemetryService,
        redis_client: redis.Redis,
        schedule_service: ScheduleService,
        ml_service: MLService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.telemetry = telemetry_service
        self.redis = redis_client
        self.schedule = schedule_service
        self.ml_service = ml_service
        self.settings = settings

    async def generate_prediction(self, tr_id: int) -> PredictionLogDto:
        history = await self.telemetry.get_history(tr_id)

        clock_str = await self.redis.get("replay:clock")
        if clock_str:
            current_time_t = datetime.fromisoformat(clock_str.decode("utf-8"))
        else:
            current_time_t = datetime.now(UTC)

        segment_avg_speed = 0.0
        idle_time_s = 0.0
        telemetry_points = []
        window_points = []
        history_sorted = []
        coverage_ratio = 0.0

        window_start = current_time_t - timedelta(
            minutes=self.settings.app.ml_telemetry_window_minutes
        )
        window_end = current_time_t

        if history:
            speeds = [p.speed for p in history]
            segment_avg_speed = sum(speeds) / len(speeds)

            history_sorted = sorted(history, key=lambda x: x.timestamp)

            for i in range(1, len(history_sorted)):
                delta = (
                    history_sorted[i].timestamp - history_sorted[i - 1].timestamp
                ).total_seconds()

                if delta > self.settings.app.max_idle_gap_s:
                    continue

                if history_sorted[i].speed < self.settings.app.stop_speed_threshold_kmh:
                    idle_time_s += max(0, delta)

            window_points = [
                p for p in history_sorted if window_start <= p.timestamp <= window_end
            ]

            telemetry_points = [
                TelemetryPoint(
                    timestamp=p.timestamp,
                    longitude=p.longitude,
                    latitude=p.latitude,
                    speed=float(p.speed),
                    course=float(p.course),
                    location_valid=p.location_valid,
                    packet_time=p.packet_time if p.packet_time else p.timestamp,
                    is_historical=p.is_historical,
                )
                for p in window_points
            ]

            expected_points = (
                self.settings.app.ml_telemetry_window_minutes * 60
            ) / 10.0
            coverage_ratio = min(1.0, len(window_points) / expected_points)

        cur_dev_s = 0.0
        previous_stop = await self.schedule.get_previous_stop(tr_id, current_time_t)

        if (
            previous_stop
            and previous_stop.longitude
            and previous_stop.latitude
            and history_sorted
        ):
            for p in reversed(history_sorted):
                dist = geopy_distance(
                    (p.latitude, p.longitude),
                    (previous_stop.latitude, previous_stop.longitude),
                ).meters

                if dist < 50.0 and p.speed < self.settings.app.stop_speed_threshold_kmh:
                    cur_dev_s = (p.timestamp - previous_stop.time_begin).total_seconds()
                    break

        next_stop = await self.schedule.get_next_stop(tr_id, current_time_t)
        if not next_stop:
            raise ValueError(f"No upcoming stops in schedule for tr_id {tr_id}")

        route_features = None
        if next_stop.longitude is not None and next_stop.latitude is not None:
            stop_times = await self.schedule.get_stop_times(tr_id)
            now = current_time_t.timestamp()
            target_time = next_stop.time_begin.timestamp()

            valid_points = [
                p
                for p in window_points
                if p.location_valid
                and all(
                    math.isfinite(v)
                    for v in (p.longitude, p.latitude, float(p.speed), float(p.course))
                )
                and -180 <= p.longitude <= 180
                and -90 <= p.latitude <= 90
                and p.longitude != 0
                and p.latitude != 0
                and 0 <= float(p.speed) <= 130
            ]

            if valid_points:
                latest = valid_points[-1]
                lon = latest.longitude
                lat = latest.latitude
                speed = float(latest.speed)
                heading = float(latest.course)
                gps_age_s = now - latest.timestamp.timestamp()

                lat1, lat2 = math.radians(lat), math.radians(next_stop.latitude)
                h = (
                    math.sin((lat2 - lat1) / 2) ** 2
                    + math.cos(lat1)
                    * math.cos(lat2)
                    * math.sin(math.radians(next_stop.longitude - lon) / 2) ** 2
                )
                distance_target_m = (
                    6371000 * 2 * math.asin(min(1, math.sqrt(max(0, h))))
                )

                east = (
                    math.radians(next_stop.longitude - lon)
                    * 6371000
                    * math.cos(math.radians((lat + next_stop.latitude) / 2))
                )
                north = math.radians(next_stop.latitude - lat) * 6371000
                bearing = math.degrees(math.atan2(east, north))

                heading_alignment = math.cos(math.radians(bearing - heading))
                route_features = RouteFeatures(
                    cur_dev_missing=0.0,
                    horizon_s=target_time - now,
                    hour_sin=math.sin(2 * math.pi * (now % 86400) / 86400),
                    hour_cos=math.cos(2 * math.pi * (now % 86400) / 86400),
                    stops_ahead=float(
                        bisect_right(stop_times, target_time)
                        - bisect_right(stop_times, now)
                    ),
                    target_lon=next_stop.longitude,
                    target_lat=next_stop.latitude,
                    distance_target_m=distance_target_m,
                    gps_age_s=gps_age_s,
                    last_lon=lon,
                    last_lat=lat,
                    last_speed=speed,
                    heading_alignment=heading_alignment,
                    target_east_m=east,
                    target_north_m=north,
                )

        ml_request = MLPredictionRequest(
            tr_id=tr_id,
            target_stop_id=next_stop.stop_id,
            target_time_begin=next_stop.time_begin,
            current_time_T=current_time_t,
            cur_dev_s=cur_dev_s,
            aggregates=TelemetryAggregates(
                segment_avg_speed=segment_avg_speed,
                idle_time_s=idle_time_s,
                coverage_ratio=coverage_ratio,
            ),
            window=TelemetryWindow(
                start_time=window_start,
                end_time=window_end,
                recent_points=telemetry_points,
            ),
            route_features=route_features,
        )

        ml_resp, error_text = await self.ml_service.get_prediction(
            ml_request, fallback_delay_s=cur_dev_s
        )

        log = await self.repository.save_prediction(
            tr_id=tr_id,
            predicted_delay_s=ml_resp.predicted_delay_s,
            risk_level=ml_resp.risk_level,
            pattern_reason=ml_resp.pattern_reason,
            error_text=error_text,
            status=ml_resp.status,
        )

        dto = PredictionLogDto(
            id=log.id,
            tr_id=log.tr_id,
            predicted_delay_s=log.predicted_delay_s,
            risk_level=RiskLevel(log.risk_level),
            pattern_reason=IncidentPattern(log.pattern_reason)
            if log.pattern_reason
            else None,
            created_at=log.created_at,
        )

        await self.redis.set(
            f"vehicle_prediction:{tr_id}",
            dto.model_dump_json(),
            ex=self.settings.app.prediction_cache_ttl,
        )

        return dto
