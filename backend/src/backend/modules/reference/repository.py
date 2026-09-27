from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DeviceMapping


class DeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_unit_id(self, unit_id: int) -> DeviceMapping | None:
        stmt = select(DeviceMapping).where(DeviceMapping.unit_id == unit_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, unit_id: int, tr_id: int) -> DeviceMapping:
        mapping = DeviceMapping(unit_id=unit_id, tr_id=tr_id)

        self.session.add(mapping)
        await self.session.flush()

        return mapping

    async def clear(self) -> None:
        stmt = delete(DeviceMapping)
        await self.session.execute(stmt)
        await self.session.flush()

    async def create_batch(self, mappings: list[DeviceMapping]) -> None:
        if not mappings:
            return

        self.session.add_all(mappings)
        await self.session.flush()
