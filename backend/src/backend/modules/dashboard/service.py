import logging
from datetime import UTC, datetime

import redis.asyncio as redis

from backend.modules.telemetry.models import RedisTelemetryRecord
from backend.modules.telemetry.service import TelemetryService
from commons.contracts.v1.api.predictions import PredictionLogDto
from commons.contracts.v1.dashboard.responses import (
    DashboardStateResponse,
    IncidentCard,
    VehicleState,
)
from commons.enums import RiskLevel

logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(
        self, redis_client: redis.Redis, telemetry_service: TelemetryService
    ) -> None:
        self.redis = redis_client
        self.telemetry = telemetry_service

    async def get_current_state(self) -> DashboardStateResponse:
        active_ids = await self.telemetry.get_active_vehicles(minutes=5)

        if not active_ids:
            return DashboardStateResponse(timestamp=datetime.now(UTC), vehicles=[])

        async with self.redis.pipeline() as pipe:
            for tr_id in active_ids:
                pipe.lindex(f"telemetry:history:{tr_id}", -1)
                pipe.get(f"vehicle_prediction:{tr_id}")

            results = await pipe.execute()

        vehicles = []
        for i, tr_id in enumerate(active_ids):
            point_json = results[i * 2]
            prediction_json = results[i * 2 + 1]

            if not point_json:
                continue

            latest_point = RedisTelemetryRecord.model_validate_json(point_json)

            risk_color = RiskLevel.GREEN
            incident_card = None

            if prediction_json:
                try:
                    prediction_log = PredictionLogDto.model_validate_json(
                        prediction_json
                    )
                    risk_color = prediction_log.risk_level

                    if risk_color != RiskLevel.GREEN:
                        incident_card = IncidentCard(
                            has_incident=True,
                            predicted_delay_s=prediction_log.predicted_delay_s,
                            reason=prediction_log.pattern_reason,
                            route_segment=f"Segment for tr_id {tr_id}",
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to parse prediction for tr_id %d: %s", tr_id, e
                    )

            vehicles.append(
                VehicleState(
                    tr_id=tr_id,
                    longitude=latest_point.longitude,
                    latitude=latest_point.latitude,
                    risk_color=risk_color,
                    incident_card=incident_card,
                )
            )

        return DashboardStateResponse(
            timestamp=datetime.now(UTC),
            vehicles=vehicles,
        )
