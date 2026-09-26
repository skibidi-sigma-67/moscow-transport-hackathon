from typing import Annotated

from fastapi import Depends

from backend.api.dependencies import DatabaseSessionDependency
from backend.modules.reference.repository import DeviceRepository
from backend.modules.reference.service import DeviceService


def get_device_service(session: DatabaseSessionDependency) -> DeviceService:
    repository = DeviceRepository(session)
    return DeviceService(repository)


DeviceServiceDependency = Annotated[DeviceService, Depends(get_device_service)]
