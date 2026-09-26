from fastapi import APIRouter, File, UploadFile

from backend.modules.reference.api.dependencies import DeviceServiceDependency
from commons.contracts.v1.api.reference import DeviceMappingDto

reference_router = APIRouter(
    prefix="/reference",
    tags=["Reference"],
)


@reference_router.post(
    "/devices",
    summary="Регистрация устройства",
    description="Регистрирует связь между идентификатором бортового оборудования (трекера) и транспортным средством в системе.",
    response_description="Созданная запись о привязке устройства к ТС",
)
async def register_device(
    unit_id: int,
    tr_id: int,
    service: DeviceServiceDependency,
) -> DeviceMappingDto:
    mapping = await service.register_device(unit_id, tr_id)
    return mapping


@reference_router.post(
    "/devices/upload",
    summary="Загрузка маппингов из CSV",
    description="Парсит файл traffic.csv на бэкенде, массово извлекая уникальные пары (unit_id, tr_id).",
    response_description="Количество успешно загруженных уникальных привязок",
)
async def upload_devices(
    service: DeviceServiceDependency,
    file: UploadFile = File(..., description="CSV файл traffic.csv"),
) -> dict[str, int]:
    count = await service.upload_devices_csv(file)
    return {"inserted_count": count}
