from typing import Annotated

from fastapi import Depends

from backend.api.dependencies import RedisClientDependency
from backend.modules.dashboard.service import DashboardService
from backend.modules.telemetry.api.dependencies import TelemetryServiceDependency


def get_dashboard_service(
    redis: RedisClientDependency, telemetry: TelemetryServiceDependency
) -> DashboardService:
    return DashboardService(redis, telemetry)


DashboardServiceDependency = Annotated[DashboardService, Depends(get_dashboard_service)]
