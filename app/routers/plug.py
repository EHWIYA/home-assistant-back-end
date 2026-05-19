from fastapi import APIRouter, Depends

from app.constants import ENTITY_PLUG_SWITCH
from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import PlugActionRequest, PlugActionResponse
from app.services.ha_client import HAClient
from app.services.status_builder import _switch_state

router = APIRouter(prefix="/api/v1", tags=["plug"])


@router.post("/plug", response_model=PlugActionResponse)
async def set_plug(
    body: PlugActionRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> PlugActionResponse:
    ha = HAClient(settings)
    service = "turn_on" if body.action == "on" else "turn_off"
    await ha.call_service("switch", service, {"entity_id": ENTITY_PLUG_SWITCH})
    state = await ha.get_state(ENTITY_PLUG_SWITCH)
    return PlugActionResponse(ok=True, switch=_switch_state(state.get("state")))
