import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.seed import seed_strip_device
from app.db.session import dispose_engine, init_engine
from app.routers import ac, health, history, meta, mood, pc, plug, schedules, status, strip, weather
from app.services.ha_ws_cache import get_ha_state_cache


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    init_engine(settings)
    if settings.strip_configured:
        await seed_strip_device(settings)
    cache = get_ha_state_cache()
    cache.start(settings)
    yield
    await cache.stop()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="iot-api",
        description="BFF for Home Assistant + Hejhome PowerStrip (iot-web)",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(status.router)
    app.include_router(plug.router)
    app.include_router(pc.router)
    app.include_router(ac.router)
    app.include_router(history.router)
    app.include_router(strip.router)
    app.include_router(schedules.router)
    app.include_router(meta.router)
    app.include_router(weather.router)
    app.include_router(mood.router)
    return app


app = create_app()
