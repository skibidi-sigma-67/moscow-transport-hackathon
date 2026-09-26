import time

import redis.asyncio as redis

from backend.settings import Settings

from .models import RedisTelemetryRecord


class TelemetryRedisRepository:
    def __init__(self, redis_client: redis.Redis, settings: Settings) -> None:
        self.redis = redis_client
        self.settings = settings

    @staticmethod
    def _get_key(unit_id: int) -> str:
        return f"telemetry:history:{unit_id}"

    async def add_point(self, unit_id: int, point: RedisTelemetryRecord) -> None:
        key = self._get_key(unit_id)
        point_json = point.model_dump_json()

        async with self.redis.pipeline() as pipe:
            pipe.rpush(key, point_json)
            pipe.ltrim(key, -self.settings.app.telemetry_max_history, -1)
            pipe.zadd("active_vehicles", {str(unit_id): point.timestamp.timestamp()})
            await pipe.execute()

    async def get_active_vehicles(self, minutes: int) -> list[int]:
        min_score = time.time() - (minutes * 60)

        raw_ids = await self.redis.zrevrangebyscore(
            "active_vehicles", "+inf", min_score
        )
        return [int(uid) for uid in raw_ids]  # type: ignore

    async def get_history(self, unit_id: int) -> list[RedisTelemetryRecord]:
        key = self._get_key(unit_id)
        raw_items = await self.redis.lrange(key, 0, -1)

        history = []
        for item in raw_items:
            history.append(RedisTelemetryRecord.model_validate_json(item))

        return history
