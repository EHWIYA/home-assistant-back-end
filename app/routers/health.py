from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.config import Settings, get_settings
from app.db.session import get_engine
from app.models.schemas import HealthResponse
from app.services.ha_client import HAClient

router = APIRouter(tags=["health"])


async def _ping_db() -> bool | None:
    engine = get_engine()
    if engine is None:
        return None
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    ha = HAClient(settings)
    reachable = await ha.ping()
    db_reachable = await _ping_db() if settings.database_url else None
    return HealthResponse(status="ok", ha_reachable=reachable, db_reachable=db_reachable)
