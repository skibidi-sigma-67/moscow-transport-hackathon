from fastapi import APIRouter, Request

from commons.contracts.v1.api.health import HealthResponse, HealthSettings

health_router = APIRouter(tags=["System"])


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка состояния системы",
    description="Возвращает статус основного приложения, статус ML-сервиса, а также текущие настройки приложения.",
)
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
