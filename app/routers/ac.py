import logging
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, Response

from app.constants import (
    AC_COMMAND_COOL_PRESET_17,
    AC_COMMAND_DRY_PRESET_17,
    AC_COMMAND_OFF,
    AC_REMOTE_DEVICE,
    ENTITY_AC_MODE,
    ENTITY_AC_REMOTE,
    ENTITY_AC_LAST_OFF,
    ENTITY_AC_LAST_ON,
)
from app.deps import ApiKeyDep, SettingsDep
from app.exceptions import HAError
from app.models.schemas import AcActionRequest, AcActionResponse, AcStateResponse
from app.services.ha_client import HAClient
from app.services.status_service import fetch_status

router = APIRouter(prefix="/api/v1", tags=["ac"])
logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


def _now_kst_input_datetime() -> str:
    # HA input_datetime.set_datetime expects "YYYY-MM-DD HH:MM:SS"
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


@router.get("/ac/state", response_model=AcStateResponse)
async def get_ac_state(
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> AcStateResponse:
    status = await fetch_status(settings)
    ha = HAClient(settings)

    mode = "off"
    try:
        raw = await ha.get_state(ENTITY_AC_MODE)
        raw_state = str(raw.get("state") or "").strip().lower()
        if raw_state in {"off", "cool", "dry"}:
            mode = raw_state
    except Exception as exc:
        logger.warning("failed to fetch ac mode: %s", exc)

    power = "on" if status.ac_estimated_running else "off"
    auto_enabled = bool(status.ac_auto_enabled)
    temperature_c = status.indoor.temperature if status.indoor else None
    humidity = status.indoor.humidity if status.indoor else None

    return AcStateResponse(
        power=power,
        mode=mode,
        auto_enabled=auto_enabled,
        temperature_c=temperature_c,
        humidity=humidity,
    )


@router.post("/ac", response_model=AcActionResponse)
async def set_ac(
    body: AcActionRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
    response: Response,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> AcActionResponse:
    request_id = x_request_id or str(uuid4())
    response.headers["X-Request-ID"] = request_id

    if body.mode == "off":
        command = AC_COMMAND_OFF
    elif body.mode == "cool":
        command = AC_COMMAND_COOL_PRESET_17
    elif body.mode == "dry":
        command = AC_COMMAND_DRY_PRESET_17
    else:
        # Pydantic validation should prevent this, but keep a safe default.
        command = AC_COMMAND_OFF

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

    # Keep HA helper entities in sync with actual control action.
    try:
        await ha.call_service(
            "input_select",
            "select_option",
            {"entity_id": ENTITY_AC_MODE, "option": body.mode},
        )
    except Exception as exc:
        logger.error(
            "ac mode sync failed request_id=%s requested_mode=%s error=%s",
            request_id,
            body.mode,
            exc,
        )
        raise HAError(
            detail="AC mode sync failed",
            status_code=502,
            code="ac_mode_sync_failed",
        ) from exc

    # Reflect manual control into HA last_on/off timestamps.
    try:
        entity_id = ENTITY_AC_LAST_ON if body.mode != "off" else ENTITY_AC_LAST_OFF
        await ha.call_service(
            "input_datetime",
            "set_datetime",
            {"entity_id": entity_id, "datetime": _now_kst_input_datetime()},
        )
    except Exception as exc:
        logger.error(
            "ac last_on_off sync failed request_id=%s requested_mode=%s error=%s",
            request_id,
            body.mode,
            exc,
        )
        raise HAError(
            detail="AC timestamp sync failed",
            status_code=502,
            code="ac_timestamp_sync_failed",
        ) from exc

    # Re-fetch to verify response consistency for frontend state update.
    status = await fetch_status(settings)
    raw_mode = await ha.get_state(ENTITY_AC_MODE)
    applied_mode = str(raw_mode.get("state") or "").strip().lower()
    if applied_mode not in {"off", "cool", "dry"}:
        logger.error(
            "ac verify failed invalid mode request_id=%s requested_mode=%s applied_mode=%s",
            request_id,
            body.mode,
            applied_mode,
        )
        raise HAError(
            detail="AC verify failed",
            status_code=502,
            code="ac_verify_failed",
        )

    if applied_mode != body.mode:
        logger.error(
            "ac verify mismatch request_id=%s requested_mode=%s applied_mode=%s",
            request_id,
            body.mode,
            applied_mode,
        )
        raise HAError(
            detail="AC state mismatch after control",
            status_code=502,
            code="ac_state_mismatch",
        )

    power = "on" if status.ac_estimated_running else "off"
    return AcActionResponse(
        request_id=request_id,
        applied_mode=applied_mode,
        power=power,
    )
