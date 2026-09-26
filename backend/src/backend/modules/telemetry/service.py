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
            location_valid=point_dto.location_valid,
            packet_time=point_dto.packet_time,
            is_historical=point_dto.is_historical,
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
                location_valid=r.location_valid,
                packet_time=r.packet_time,
                is_historical=r.is_historical,
            )
            for r in records
        ]

    async def get_active_vehicles(self, minutes: int = 5) -> list[int]:
        return await self.repository.get_active_vehicles(minutes)

    async def get_latest_point(self, unit_id: int) -> TelemetryPointDto | None:
        record = await self.repository.get_latest_point(unit_id)
        if not record:
            return None

        return TelemetryPointDto(
            timestamp=record.timestamp,
            longitude=record.longitude,
            latitude=record.latitude,
            speed=record.speed,
            course=record.course,
            location_valid=record.location_valid,
            packet_time=record.packet_time,
            is_historical=record.is_historical,
        )
