from datetime import UTC, datetime

import httpx
import redis.asyncio as redis

from backend.modules.schedule.service import ScheduleService
from backend.modules.telemetry.service import TelemetryService
from backend.settings import Settings
from commons.contracts.v1.api.predictions import PredictionLogDto
from commons.contracts.v1.ml.requests import MLPredictionRequest, TelemetryPoint
from commons.contracts.v1.ml.responses import MLPredictionResponse
from commons.enums import RiskLevel

from .repository import PredictionRepository


class PredictionService:
    def __init__(
        self,
        repository: PredictionRepository,
        telemetry_service: TelemetryService,
        redis_client: redis.Redis,
        schedule_service: ScheduleService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.telemetry = telemetry_service
        self.redis = redis_client
        self.schedule = schedule_service
        self.settings = settings

    async def generate_prediction(self, tr_id: int) -> PredictionLogDto:
        history = await self.telemetry.get_history(tr_id)

        segment_avg_speed = 0.0
        idle_time_s = 0.0
        telemetry_points = []
        history_sorted = []

        if history:
            speeds = [p.speed for p in history]
            segment_avg_speed = sum(speeds) / len(speeds)

            history_sorted = sorted(history, key=lambda x: x.timestamp)

            for i in range(1, len(history_sorted)):
                if history_sorted[i].speed < 3:
                    delta = (
                        history_sorted[i].timestamp - history_sorted[i - 1].timestamp
                    ).total_seconds()
                    idle_time_s += max(0, delta)

            telemetry_points = [
                TelemetryPoint(
                    timestamp=p.timestamp,
                    longitude=p.longitude,
                    latitude=p.latitude,
                    speed=float(p.speed),
                    course=float(p.course),
                )
                for p in history_sorted[-20:]
            ]

        current_time_t = (
            history_sorted[-1].timestamp if history_sorted else datetime.now(UTC)
        )

        next_stop = await self.schedule.get_next_stop(tr_id, current_time_t)
        if not next_stop:
            raise ValueError(f"No upcoming stops in schedule for tr_id {tr_id}")

        ml_request = MLPredictionRequest(
            tr_id=tr_id,
            target_stop_id=next_stop.stop_id,
            target_time_begin=next_stop.time_begin,
            current_time_T=current_time_t,
            cur_dev_s=0.0,
            segment_avg_speed=segment_avg_speed,
            idle_time_s=idle_time_s,
            recent_telemetry=telemetry_points,
        )

        try:
            async with httpx.AsyncClient(timeout=self.settings.ml.timeout) as client:
                resp = await client.post(
                    self.settings.ml.url,
                    json=ml_request.model_dump(mode="json"),
                )
                resp.raise_for_status()
                ml_resp = MLPredictionResponse.model_validate_json(resp.read())
        except Exception as e:
            ml_resp = MLPredictionResponse(
                predicted_delay_s=0.0,
                risk_level=RiskLevel.GREEN,
                pattern_reason=f"ML Error: {e}",
            )

        log = await self.repository.save_prediction(
            tr_id=tr_id,
            predicted_delay_s=ml_resp.predicted_delay_s,
            risk_level=ml_resp.risk_level,
            pattern_reason=ml_resp.pattern_reason,
        )

        dto = PredictionLogDto(
            id=log.id,
            tr_id=log.tr_id,
            predicted_delay_s=log.predicted_delay_s,
            risk_level=RiskLevel(log.risk_level),
            pattern_reason=log.pattern_reason,
            created_at=log.created_at,
        )

        await self.redis.setex(
            f"vehicle_prediction:{tr_id}",
            self.settings.app.prediction_cache_ttl,
            dto.model_dump_json(),
        )

        return dto
