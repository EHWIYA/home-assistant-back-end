from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.schemas import StatusResponse
from app.services.ha_client import HAClient
from app.services.status_builder import fetch_and_build_status

router = APIRouter(prefix="/api/v1", tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def get_status(
    settings: Settings = Depends(get_settings),
) -> StatusResponse:
    ha = HAClient(settings)
    return await fetch_and_build_status(ha, settings)
