from fastapi import APIRouter, Depends

from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import StatusResponse
from app.services.ha_client import HAClient
from app.services.status_builder import fetch_and_build_status

router = APIRouter(prefix="/api/v1", tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def get_status(
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> StatusResponse:
    ha = HAClient(settings)
    return await fetch_and_build_status(ha, settings)
