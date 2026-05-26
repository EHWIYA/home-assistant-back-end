import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from app.constants import (
    AC_COMMAND_OFF,
    AC_COMMAND_ON,
    AC_REMOTE_DEVICE,
    ENTITY_AC_REMOTE,
    ENTITY_AC_LAST_OFF,
    ENTITY_AC_LAST_ON,
)
from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import AcActionRequest, AcActionResponse
from app.services.ha_client import HAClient

router = APIRouter(prefix="/api/v1", tags=["ac"])
logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


def _now_kst_input_datetime() -> str:
    # HA input_datetime.set_datetime expects "YYYY-MM-DD HH:MM:SS"
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


@router.post("/ac", response_model=AcActionResponse)
async def set_ac(
    body: AcActionRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> AcActionResponse:
    command = AC_COMMAND_ON if body.action == "on" else AC_COMMAND_OFF
    ha = HAClient(settings)
    await ha.call_service(
        "remote",
        "send_command",
        {
            "entity_id": ENTITY_AC_REMOTE,
            "device": AC_REMOTE_DEVICE,
            "command": command,
        },
    )

    # Option 2-A: reflect manual control into HA last_on/off timestamps (best-effort).
    try:
        entity_id = ENTITY_AC_LAST_ON if body.action == "on" else ENTITY_AC_LAST_OFF
        await ha.call_service(
            "input_datetime",
            "set_datetime",
            {"entity_id": entity_id, "datetime": _now_kst_input_datetime()},
        )
    except Exception as exc:
        logger.warning("failed to update ac last_on/off: %s", exc)
    return AcActionResponse()
