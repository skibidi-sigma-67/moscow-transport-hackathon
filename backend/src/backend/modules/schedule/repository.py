from datetime import datetime

from sqlalchemy import select
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
            .where(SchedulePlan.tr_id == tr_id, SchedulePlan.time_begin >= current_time)
            .order_by(SchedulePlan.time_begin.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_batch(self, plans: list[SchedulePlan]) -> None:
        self.session.add_all(plans)
        await self.session.flush()
