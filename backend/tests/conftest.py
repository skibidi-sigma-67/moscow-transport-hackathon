from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
import redis.asyncio as redis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from backend.api.dependencies import get_database_session, get_redis_client
from backend.bootstrap import create_app
from backend.database.base import Base
from backend.settings import Settings


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as asyncio")


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7-alpine") as redis_server:
        yield redis_server


@pytest_asyncio.fixture(scope="session")
async def engine(postgres_container: PostgresContainer):
    url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2", "postgresql+asyncpg"
    )
    engine = create_async_engine(url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def redis_client(redis_container: RedisContainer) -> AsyncGenerator[redis.Redis]:
    url = f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0"
    client = redis.Redis.from_url(url, decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession]:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session


from backend.modules.ml.service import MLService


@pytest_asyncio.fixture
async def app_client(engine, redis_client) -> AsyncGenerator[AsyncClient]:
    app = create_app()
    app.state.settings = Settings()
    app.state.ml_service = MLService(app.state.settings)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.session_maker = maker
    app.state.redis_client = redis_client

    async def override_get_db():
        async with maker() as session:
            yield session

    async def override_get_redis():
        yield redis_client

    app.dependency_overrides[get_database_session] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
