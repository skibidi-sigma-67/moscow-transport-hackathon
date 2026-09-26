from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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

    async def bulk_create_if_not_exists(self, mappings: list[dict[str, int]]) -> int:
        if not mappings:
            return 0

        stmt = (
            insert(DeviceMapping)
            .values(mappings)
            .on_conflict_do_nothing(index_elements=["unit_id"])
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
