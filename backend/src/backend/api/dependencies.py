from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_database_session(request: Request) -> AsyncGenerator[AsyncSession]:
    session_maker: async_sessionmaker[AsyncSession] = request.app.state.session_maker

    async with session_maker() as session, session.begin():
        yield session


async def get_redis_client(request: Request) -> AsyncGenerator[redis.Redis]:
    redis_client: redis.Redis = request.app.state.redis_client
    yield redis_client


DatabaseSessionDependency = Annotated[AsyncSession, Depends(get_database_session)]
RedisClientDependency = Annotated[redis.Redis, Depends(get_redis_client)]
