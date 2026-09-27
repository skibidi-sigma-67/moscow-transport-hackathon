from fastapi import APIRouter

from backend.api.v1.health import health_router
from backend.modules.dashboard import dashboard_router
from backend.modules.predictions import predictions_router
from backend.modules.reference import reference_router
from backend.modules.schedule.api.router import schedule_router
from backend.modules.telemetry import telemetry_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(reference_router)
v1_router.include_router(telemetry_router)
v1_router.include_router(predictions_router)
v1_router.include_router(dashboard_router)
v1_router.include_router(schedule_router)
v1_router.include_router(health_router)
