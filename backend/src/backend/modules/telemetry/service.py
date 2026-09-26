from commons.contracts.v1.api.telemetry import TelemetryPointDto

from .models import RedisTelemetryRecord
from .repository import TelemetryRedisRepository


class TelemetryService:
    def __init__(self, repository: TelemetryRedisRepository) -> None:
        self.repository = repository

    async def add_point(self, unit_id: int, point_dto: TelemetryPointDto) -> None:
        record = RedisTelemetryRecord(
            timestamp=point_dto.timestamp,
            longitude=point_dto.longitude,
            latitude=point_dto.latitude,
            speed=point_dto.speed,
            course=point_dto.course,
        )
        await self.repository.add_point(unit_id, record)

    async def get_history(self, unit_id: int) -> list[TelemetryPointDto]:
        records = await self.repository.get_history(unit_id)
        return [
            TelemetryPointDto(
                timestamp=r.timestamp,
                longitude=r.longitude,
                latitude=r.latitude,
                speed=r.speed,
                course=r.course,
            )
            for r in records
        ]

    async def get_active_vehicles(self, minutes: int = 5) -> list[int]:
        return await self.repository.get_active_vehicles(minutes)

    async def get_latest_point(self, unit_id: int) -> TelemetryPointDto | None:
        history = await self.get_history(unit_id)
        if not history:
            return None

        return history[-1]
