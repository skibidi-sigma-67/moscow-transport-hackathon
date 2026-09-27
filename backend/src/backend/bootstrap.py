import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.v1.router import v1_router
from backend.database.engine import create_engine, create_session_maker
from backend.modules.dashboard.service import DashboardService
from backend.modules.dashboard.websocket_pool import WebsocketConnectionPool
from backend.modules.dashboard.worker import DashboardWorker
from backend.modules.ml.service import MLService
from backend.modules.predictions.worker import PredictionWorker
from backend.modules.telemetry.repository import TelemetryRedisRepository
from backend.modules.telemetry.service import TelemetryService
from backend.ndtp.server import NdtpServer
from backend.redis.client import create_redis_pool
from backend.settings import get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    engine = create_engine(settings.database, debug=settings.app.debug)
    app.state.session_maker = create_session_maker(engine)
    app.state.engine = engine
    app.state.settings = settings

    redis_client = create_redis_pool(settings.redis)
    app.state.redis_client = redis_client

    ndtp_server = NdtpServer(
        host=settings.ndtp.host,
        port=settings.ndtp.port,
        session_maker=app.state.session_maker,
        redis_client=app.state.redis_client,
        settings=settings,
    )

    ml_service = MLService(settings)
    app.state.ml_service = ml_service

    prediction_worker = PredictionWorker(
        name="ml_predictions",
        redis_client=app.state.redis_client,
        session_maker=app.state.session_maker,
        settings=settings,
        ml_service=app.state.ml_service,
        target_cycle_time_s=30.0,
    )

    app.state.dashboard_websocket_pool = WebsocketConnectionPool()
    telemetry_repo = TelemetryRedisRepository(app.state.redis_client, settings)
    telemetry_service = TelemetryService(telemetry_repo)
    dashboard_service = DashboardService(app.state.redis_client, telemetry_service)

    dashboard_worker = DashboardWorker(
        name="dashboard_websocket",
        service=dashboard_service,
        websocket_pool=app.state.dashboard_websocket_pool,
        settings=settings,
    )

    await ndtp_server.start()
    await prediction_worker.start()
    await dashboard_worker.start()

    yield

    try:
        async with asyncio.timeout(5.0):
            await dashboard_worker.stop()
            await prediction_worker.stop()
            await ndtp_server.stop()
    except TimeoutError:
        pass

    await engine.dispose()
    await redis_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app.title,
        debug=settings.app.debug,
        lifespan=_lifespan,
    )

    app.include_router(v1_router)

    return app
