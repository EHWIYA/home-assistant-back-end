from fastapi import APIRouter, Query

from app.config import get_settings
from app.deps import ApiKeyDep
from app.models.schemas import HolidaysResponse
from app.services.kr_holidays import get_holidays_for_year

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


@router.get("/holidays", response_model=HolidaysResponse)
async def list_holidays(
    _key: ApiKeyDep,
    year: int = Query(ge=2000, le=2100),
) -> HolidaysResponse:
    settings = get_settings()
    payload = get_holidays_for_year(year, data_dir=settings.kr_holidays_dir)
    return HolidaysResponse(**payload)
