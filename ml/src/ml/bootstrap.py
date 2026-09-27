from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ml.api.router import router
from ml.models.predictor import Predictor
from ml.settings import get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    app.state.predictor = Predictor(settings.app.model_dir, settings.app.strategy)
    app.state.settings = settings

    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app.title,
        version=settings.app.version,
        debug=settings.app.debug,
        lifespan=_lifespan,
    )
    app.include_router(router)

    return app
