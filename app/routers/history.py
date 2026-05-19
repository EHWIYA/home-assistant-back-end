from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query

from app.constants import ENTITY_PLUG_POWER
from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import PowerHistoryPoint, PowerHistoryResponse
from app.services.ha_client import HAClient
from app.services.status_builder import _parse_float

router = APIRouter(prefix="/api/v1", tags=["history"])

KST = ZoneInfo("Asia/Seoul")


def _to_kst_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(KST).isoformat(timespec="seconds")


@router.get("/history/power", response_model=PowerHistoryResponse)
async def power_history(
    _key: ApiKeyDep,
    settings: SettingsDep,
    hours: int = Query(default=24, ge=1, le=168),
) -> PowerHistoryResponse:
    ha = HAClient(settings)
    raw = await ha.get_history(ENTITY_PLUG_POWER, hours=hours)

    points: list[PowerHistoryPoint] = []
    # HA returns [[{state, last_changed, ...}, ...]] per entity
    for series in raw:
        for entry in series:
            last_changed = entry.get("last_changed") or entry.get("last_updated")
            if not last_changed:
                continue
            dt = datetime.fromisoformat(str(last_changed).replace("Z", "+00:00"))
            w = _parse_float(entry.get("state"))
            points.append(PowerHistoryPoint(t=_to_kst_iso(dt), w=w))

    return PowerHistoryResponse(points=points)
