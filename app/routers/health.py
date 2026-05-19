from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.schemas import HealthResponse
from app.services.ha_client import HAClient

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    ha = HAClient(settings)
    reachable = await ha.ping()
    return HealthResponse(status="ok", ha_reachable=reachable)
