import uvicorn

from backend.bootstrap import create_app
from backend.settings import get_settings

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
    )
