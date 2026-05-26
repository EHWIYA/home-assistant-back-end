from __future__ import annotations

from app.config import Settings
from app.models.schemas import StatusResponse
from app.services.ha_client import HAClient
from app.services.ha_ws_cache import get_ha_state_cache
from app.services.status_builder import fetch_and_build_status


async def fetch_status(settings: Settings) -> StatusResponse:
    """Status from HA WebSocket cache when connected; otherwise REST bulk."""
    cache = get_ha_state_cache()
    if cache.use_cache:
        return cache.build_status(settings)
    ha = HAClient(settings)
    return await fetch_and_build_status(ha, settings)
