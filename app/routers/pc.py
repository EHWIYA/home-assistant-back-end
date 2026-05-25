from fastapi import APIRouter, Depends

from app.constants import ENTITY_PC_SWITCH
from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import PcActionRequest, PcActionResponse
from app.services.ha_client import HAClient
from app.services.status_builder import _switch_state

router = APIRouter(prefix="/api/v1", tags=["pc"])


@router.post("/pc", response_model=PcActionResponse)
async def set_pc(
    body: PcActionRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> PcActionResponse:
    ha = HAClient(settings)
    service = "turn_on" if body.action == "on" else "turn_off"
    await ha.call_service("switch", service, {"entity_id": ENTITY_PC_SWITCH})
    state = await ha.get_state(ENTITY_PC_SWITCH)
    return PcActionResponse(ok=True, switch=_switch_state(state.get("state")))
