from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.modules.dashboard.api.dependencies import DashboardWebsocketPoolDependency

websocket_router = APIRouter()


@websocket_router.websocket("/websocket")
async def dashboard_websocket(
    websocket: WebSocket,
    pool: DashboardWebsocketPoolDependency,
):
    await pool.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pool.disconnect(websocket)
