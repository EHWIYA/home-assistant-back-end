from fastapi import FastAPI

from app.config import get_settings
from app.routers import health, history, plug, status


def create_app() -> FastAPI:
    app = FastAPI(
        title="iot-api",
        description="BFF for Home Assistant (iot-web)",
        version="1.0.0",
    )
    app.include_router(health.router)
    app.include_router(status.router)
    app.include_router(plug.router)
    app.include_router(history.router)
    return app


app = create_app()
