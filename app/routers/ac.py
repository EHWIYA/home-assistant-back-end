from fastapi import APIRouter

from app.constants import (
    AC_COMMAND_OFF,
    AC_COMMAND_ON,
    AC_REMOTE_DEVICE,
    ENTITY_AC_REMOTE,
)
from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import AcActionRequest, AcActionResponse
from app.services.ha_client import HAClient

router = APIRouter(prefix="/api/v1", tags=["ac"])


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
    return AcActionResponse()
