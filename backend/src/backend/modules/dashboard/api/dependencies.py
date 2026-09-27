from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request, WebSocket

from backend.api.dependencies import RedisClientDependency
from backend.modules.dashboard.service import DashboardService

if TYPE_CHECKING:
    from backend.modules.dashboard.websocket_pool import WebsocketConnectionPool
from backend.modules.telemetry.api.dependencies import TelemetryServiceDependency


def get_dashboard_service(
    redis: RedisClientDependency, telemetry: TelemetryServiceDependency
) -> DashboardService:
    return DashboardService(redis, telemetry)


DashboardServiceDependency = Annotated[DashboardService, Depends(get_dashboard_service)]


def get_dashboard_websocket_pool(websocket: WebSocket) -> "WebsocketConnectionPool":
    return websocket.app.state.dashboard_websocket_pool


DashboardWebsocketPoolDependency = Annotated[
    "WebsocketConnectionPool", Depends(get_dashboard_websocket_pool)
]
