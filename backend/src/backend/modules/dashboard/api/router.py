from fastapi import APIRouter

from backend.modules.dashboard.api.dependencies import DashboardServiceDependency
from commons.contracts.v1.dashboard.responses import DashboardStateResponse

dashboard_router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@dashboard_router.get(
    "/state",
    summary="Получить состояние дашборда",
    description="Агрегирует текущее состояние всех активных транспортных средств на линии, их последние координаты и свежие предсказания от ML-модели.",
    response_description="Общее состояние всех транспортных средств",
)
async def get_dashboard_state(
    service: DashboardServiceDependency,
) -> DashboardStateResponse:
    return await service.get_current_state()
