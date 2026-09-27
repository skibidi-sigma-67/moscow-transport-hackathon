from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import SchedulePlan


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_next_stop(
        self, tr_id: int, current_time: datetime
    ) -> SchedulePlan | None:
        stmt = (
            select(SchedulePlan)
            .where(
                SchedulePlan.tr_id == tr_id,
                SchedulePlan.time_begin > current_time + timedelta(seconds=600),
                SchedulePlan.time_begin <= current_time + timedelta(seconds=900),
            )
            .order_by(SchedulePlan.time_begin.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_previous_stop(
        self, tr_id: int, current_time: datetime
    ) -> SchedulePlan | None:
        stmt = (
            select(SchedulePlan)
            .where(SchedulePlan.tr_id == tr_id, SchedulePlan.time_begin <= current_time)
            .order_by(SchedulePlan.time_begin.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_stop_plan(self, tr_id: int, stop_id: int) -> SchedulePlan | None:
        stmt = (
            select(SchedulePlan)
            .where(SchedulePlan.tr_id == tr_id, SchedulePlan.stop_id == stop_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_stop_times(self, tr_id: int) -> list[float]:
        stmt = (
            select(SchedulePlan.time_begin)
            .where(SchedulePlan.tr_id == tr_id)
            .order_by(SchedulePlan.time_begin.asc())
        )
        result = await self.session.execute(stmt)
        return [row.timestamp() for row in result.scalars().all()]

    async def clear(self) -> None:
        stmt = delete(SchedulePlan)
        await self.session.execute(stmt)
        await self.session.flush()

    async def create_batch(self, plans: list[SchedulePlan]) -> None:
        self.session.add_all(plans)
        await self.session.flush()
