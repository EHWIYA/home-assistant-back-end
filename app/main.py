from fastapi import FastAPI

from app.config import get_settings


def create_app() -> FastAPI:
    return FastAPI(
        title="iot-api",
        description="BFF for Home Assistant (iot-web)",
        version="1.0.0",
    )


app = create_app()
