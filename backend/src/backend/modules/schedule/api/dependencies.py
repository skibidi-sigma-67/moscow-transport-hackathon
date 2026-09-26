from typing import Annotated

from fastapi import Depends

from backend.api.dependencies import DatabaseSessionDependency
from backend.modules.schedule.repository import ScheduleRepository
from backend.modules.schedule.service import ScheduleService


def get_schedule_service(session: DatabaseSessionDependency) -> ScheduleService:
    repository = ScheduleRepository(session)
    return ScheduleService(repository)


ScheduleServiceDependency = Annotated[ScheduleService, Depends(get_schedule_service)]
