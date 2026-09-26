from datetime import UTC, datetime

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.modules.schedule.api.dependencies import ScheduleServiceDependency
from commons.contracts.v1.api.schedule import SchedulePlanDto

schedule_router = APIRouter(
    prefix="/schedule",
    tags=["Schedule"],
)


@schedule_router.get(
    "/{tr_id}/next",
    summary="Следующая остановка по расписанию",
    description="Возвращает информацию о следующей плановой остановке для транспортного средства, основываясь на текущем времени.",
    response_description="Информация о следующей остановке",
)
async def get_next_stop(
    tr_id: int,
    service: ScheduleServiceDependency,
) -> SchedulePlanDto:
    now = datetime.now(UTC)
    result = await service.get_next_stop(tr_id, now)

    if not result:
        raise HTTPException(
            status_code=404, detail="No upcoming stops found for this vehicle"
        )

    return result


@schedule_router.post(
    "/upload",
    summary="Загрузка расписания в формате CSV",
    description="Позволяет массово загрузить расписание движения транспортных средств в систему из CSV файла.",
    response_description="Количество успешно загруженных записей",
)
async def upload_schedule(
    service: ScheduleServiceDependency,
    file: UploadFile = File(..., description="CSV файл с расписанием"),
) -> dict[str, int]:
    count = await service.upload_schedule_csv(file)
    return {"inserted_count": count}
