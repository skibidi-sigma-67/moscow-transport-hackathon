import csv
import re
from datetime import UTC, datetime, timedelta
from io import StringIO

from fastapi import UploadFile

from commons.contracts.v1.api.schedule import SchedulePlanDto

from .models import SchedulePlan
from .repository import ScheduleRepository


class ScheduleService:
    def __init__(self, repository: ScheduleRepository) -> None:
        self.repository = repository

    async def get_next_stop(
        self, tr_id: int, current_time: datetime
    ) -> SchedulePlanDto | None:
        plan = await self.repository.get_next_stop(tr_id, current_time)
        if not plan:
            return None

        return SchedulePlanDto.model_validate(plan)

    async def get_previous_stop(
        self, tr_id: int, current_time: datetime
    ) -> SchedulePlanDto | None:
        plan = await self.repository.get_previous_stop(tr_id, current_time)
        if not plan:
            return None

        return SchedulePlanDto.model_validate(plan)

    async def get_stop_plan(self, tr_id: int, stop_id: int) -> SchedulePlanDto | None:
        plan = await self.repository.get_stop_plan(tr_id, stop_id)
        if not plan:
            return None

        return SchedulePlanDto.model_validate(plan)

    async def get_stop_times(self, tr_id: int) -> list[float]:
        return await self.repository.get_stop_times(tr_id)

    async def upload_schedule_csv(self, file: UploadFile) -> int:
        content = await file.read()
        text = content.decode("utf-8")

        reader = csv.DictReader(StringIO(text))
        plans = []

        for row in reader:
            lon, lat = None, None
            geom = row.get("geom", "")

            if geom:
                match = re.search(r"POINT\s*\(([^ ]+)\s+([^)]+)\)", geom)
                if match:
                    lon = float(match.group(1))
                    lat = float(match.group(2))

            time_begin_str = row.get("time_begin")
            if not time_begin_str:
                continue

            clean_time_str = time_begin_str[:19]
            try:
                time_begin = datetime.strptime(
                    clean_time_str, "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=UTC)

                now_date = datetime.now(UTC).date()
                schedule_date = time_begin.date()
                days_diff = (now_date - schedule_date).days
                time_begin = time_begin + timedelta(days=days_diff)

            except ValueError:
                print(f"FAILED TO PARSE: {time_begin_str!r}")
                raise

            plan = SchedulePlan(
                tr_id=int(row["tr_id"]),
                stop_id=int(row["tt_action_item_id"]),
                time_begin=time_begin,
                address=row.get("building_address"),
                longitude=lon,
                latitude=lat,
            )
            plans.append(plan)

        if plans:
            await self.repository.clear()
            await self.repository.create_batch(plans)

        return len(plans)
