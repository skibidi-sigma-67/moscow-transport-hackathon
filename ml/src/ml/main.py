import uvicorn

from ml.bootstrap import create_app
from ml.settings import get_settings

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "ml.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
        workers=settings.app.workers,
    )
