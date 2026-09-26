from typing import Annotated

from fastapi import Depends, Request

from backend.api.dependencies import DatabaseSessionDependency, RedisClientDependency
from backend.modules.predictions.repository import PredictionRepository
from backend.modules.predictions.service import PredictionService
from backend.modules.schedule.api.dependencies import ScheduleServiceDependency
from backend.modules.telemetry.api.dependencies import TelemetryServiceDependency


def get_prediction_service(
    request: Request,
    session: DatabaseSessionDependency,
    telemetry_service: TelemetryServiceDependency,
    redis_client: RedisClientDependency,
    schedule_service: ScheduleServiceDependency,
) -> PredictionService:
    repository = PredictionRepository(session)
    settings = request.app.state.settings
    return PredictionService(
        repository, telemetry_service, redis_client, schedule_service, settings
    )


PredictionServiceDependency = Annotated[
    PredictionService, Depends(get_prediction_service)
]
