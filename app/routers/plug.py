from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Response

from app.constants import (
    ENTITY_AC_PLUG_CUT_SAFE,
    ENTITY_AC_SOFT_OFF,
    ENTITY_PLUG_POWER,
    ENTITY_PLUG_SWITCH,
)
from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import PlugActionRequest, PlugActionResponse
from app.services.ha_client import HAClient
from app.services.status_builder import _switch_state

router = APIRouter(prefix="/api/v1", tags=["plug"])


def _raise_plug_http_error(
    *,
    request_id: str,
    detail: str,
    code: str,
    status_code: int = 409,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"detail": detail, "code": code},
        headers={"X-Request-ID": request_id},
    )


async def _plug_cut_safe(ha: HAClient, *, ac_power_threshold_w: float) -> bool:
    """AC 가동 중 플러그 hard-cut 방지 게이트. soft-off/plug_cut_safe 우선, 없으면 전력 폴백."""
    cut = await ha.get_state(ENTITY_AC_PLUG_CUT_SAFE)
    cut_state = str(cut.get("state") or "").strip().lower()
    if cut_state in {"on", "true"}:
        return True
    if cut_state in {"off", "false"}:
        return False

    soft = await ha.get_state(ENTITY_AC_SOFT_OFF)
    soft_state = str(soft.get("state") or "").strip().lower()
    if soft_state in {"on", "true"}:
        return True

    power_raw = await ha.get_state(ENTITY_PLUG_POWER)
    try:
        power_w = float(power_raw.get("state"))
    except (TypeError, ValueError):
        return False
    return power_w < ac_power_threshold_w


@router.post("/plug", response_model=PlugActionResponse)
async def set_plug(
    body: PlugActionRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
    response: Response,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> PlugActionResponse:
    request_id = x_request_id or str(uuid4())
    response.headers["X-Request-ID"] = request_id

    ha = HAClient(settings)
    if body.action == "off":
        if not await _plug_cut_safe(ha, ac_power_threshold_w=settings.ac_power_threshold_w):
            _raise_plug_http_error(
                request_id=request_id,
                detail=(
                    "Plug OFF blocked: AC not soft-off yet "
                    "(power still >= threshold). Use IR OFF first, then retry."
                ),
                code="plug_cut_unsafe",
            )

    service = "turn_on" if body.action == "on" else "turn_off"
    await ha.call_service("switch", service, {"entity_id": ENTITY_PLUG_SWITCH})
    state = await ha.get_state(ENTITY_PLUG_SWITCH)
    return PlugActionResponse(ok=True, switch=_switch_state(state.get("state")))
