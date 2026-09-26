import csv
import re
from datetime import UTC, datetime
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

            try:
                time_begin = datetime.strptime(
                    time_begin_str, "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=UTC)
            except ValueError:
                time_begin = datetime.strptime(
                    time_begin_str, "%Y-%m-%d %H:%M:%S.%f"
                ).replace(tzinfo=UTC)

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
            await self.repository.create_batch(plans)

        return len(plans)
