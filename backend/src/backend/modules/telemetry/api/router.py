from fastapi import APIRouter

from backend.modules.telemetry.api.dependencies import TelemetryServiceDependency
from commons.contracts.v1.api.telemetry import TelemetryPointDto

telemetry_router = APIRouter(
    prefix="/telemetry",
    tags=["Telemetry"],
)


@telemetry_router.get(
    "/{unit_id}/history",
    summary="История телеметрии устройства",
    description="Возвращает историю перемещений (телеметрию) для указанного идентификатора трекера (бортового устройства) за последнее время.",
    response_description="Список исторических точек телеметрии",
)
async def get_telemetry_history(
    unit_id: int,
    service: TelemetryServiceDependency,
) -> list[TelemetryPointDto]:
    return await service.get_history(unit_id)
