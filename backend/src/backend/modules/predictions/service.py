from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from geopy.distance import distance as geopy_distance

from backend.modules.ml.service import MLService
from backend.modules.schedule.service import ScheduleService
from backend.modules.telemetry.service import TelemetryService
from backend.settings import Settings
from commons.contracts.v1.api.predictions import PredictionLogDto
from commons.contracts.v1.ml.requests import MLPredictionRequest, TelemetryPoint
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

        ml_request = MLPredictionRequest(
            tr_id=tr_id,
            target_stop_id=next_stop.stop_id,
            target_time_begin=next_stop.time_begin,
            current_time_T=current_time_t,
            cur_dev_s=cur_dev_s,
            segment_avg_speed=segment_avg_speed,
            idle_time_s=idle_time_s,
            window_start_time=window_start,
            window_end_time=window_end,
            coverage_ratio=coverage_ratio,
            recent_telemetry=telemetry_points,
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

        await self.redis.setex(
            f"vehicle_prediction:{tr_id}",
            self.settings.app.prediction_cache_ttl,
            dto.model_dump_json(),
        )

        return dto
