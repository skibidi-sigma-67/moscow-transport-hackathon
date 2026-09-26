from typing import Annotated

from fastapi import Depends, Request

from backend.api.dependencies import RedisClientDependency
from backend.modules.telemetry.repository import TelemetryRedisRepository
from backend.modules.telemetry.service import TelemetryService


def get_telemetry_service(
    request: Request, redis: RedisClientDependency
) -> TelemetryService:
    settings = request.app.state.settings
    repository = TelemetryRedisRepository(redis, settings)
    return TelemetryService(repository)


TelemetryServiceDependency = Annotated[TelemetryService, Depends(get_telemetry_service)]
