import redis.asyncio as redis

from backend.settings import RedisSettings


def create_redis_pool(settings: RedisSettings) -> redis.Redis:
    return redis.Redis.from_url(
        settings.url,
        decode_responses=True,
    )
