from datetime import UTC, datetime

import redis.asyncio as redis

from backend.modules.telemetry.service import TelemetryService
from commons.contracts.v1.api.predictions import PredictionLogDto
from commons.contracts.v1.dashboard.responses import (
    DashboardStateResponse,
    IncidentCard,
    VehicleState,
)
from commons.enums import RiskLevel


class DashboardService:
    def __init__(
        self, redis_client: redis.Redis, telemetry_service: TelemetryService
    ) -> None:
        self.redis = redis_client
        self.telemetry = telemetry_service

    async def get_current_state(self) -> DashboardStateResponse:
        active_ids = await self.telemetry.get_active_vehicles(minutes=5)

        vehicles = []
        for tr_id in active_ids:
            latest_point = await self.telemetry.get_latest_point(tr_id)
            if not latest_point:
                continue

            prediction_json = await self.redis.get(f"vehicle_prediction:{tr_id}")

            risk_color = RiskLevel.GREEN
            incident_card = None

            if prediction_json:
                pred = PredictionLogDto.model_validate_json(prediction_json)
                risk_color = pred.risk_level

                if risk_color != RiskLevel.GREEN:
                    incident_card = IncidentCard(
                        has_incident=True,
                        predicted_delay_s=pred.predicted_delay_s,
                        reason=pred.pattern_reason,
                        route_segment=f"Segment for tr_id {tr_id}",
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
