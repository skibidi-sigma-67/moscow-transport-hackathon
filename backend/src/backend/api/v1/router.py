from fastapi import APIRouter, Request

from backend.modules.dashboard import dashboard_router
from backend.modules.predictions import predictions_router
from backend.modules.reference import reference_router
from backend.modules.schedule.api.router import schedule_router
from backend.modules.telemetry import telemetry_router
from commons.contracts.v1.api.health import HealthResponse, HealthSettings

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(reference_router)
v1_router.include_router(telemetry_router)
v1_router.include_router(predictions_router)
v1_router.include_router(dashboard_router)
v1_router.include_router(schedule_router)


@v1_router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    settings = request.app.state.settings
    ml_service = request.app.state.ml_service

    ml_status = await ml_service.check_health()

    return HealthResponse(
        status="ok",
        ml_status=ml_status,
        settings=HealthSettings(
            prediction_cache_ttl=settings.app.prediction_cache_ttl,
            telemetry_max_history=settings.app.telemetry_max_history,
            stop_speed_threshold_kmh=settings.app.stop_speed_threshold_kmh,
            ml_telemetry_window_minutes=settings.app.ml_telemetry_window_minutes,
            max_idle_gap_s=settings.app.max_idle_gap_s,
            historical_packet_delay_s=settings.app.historical_packet_delay_s,
            dashboard_websocket_update_interval_s=settings.app.dashboard_websocket_update_interval_s,
        ),
    )
