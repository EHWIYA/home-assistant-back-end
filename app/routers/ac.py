import logging
from datetime import datetime
from threading import Lock
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, Response

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
from app.models.schemas import AcActionRequest, AcActionResponse, AcStateResponse
from app.services.ha_client import HAClient
from app.services.status_service import fetch_status

router = APIRouter(prefix="/api/v1", tags=["ac"])
logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
AC_STATE_SOURCE = "composed(power_estimation,ha_input_select,ac_auto_sensor)"
_control_state_lock = Lock()
_last_control: dict[str, str] | None = None


def _now_kst_input_datetime() -> str:
    # HA input_datetime.set_datetime expects "YYYY-MM-DD HH:MM:SS"
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def _remember_control(mode: str, result: Literal["success", "failed"]) -> None:
    global _last_control
    with _control_state_lock:
        _last_control = {
            "mode": mode,
            "result": result,
            "at": datetime.now(KST).isoformat(timespec="seconds"),
        }


def _read_last_control() -> dict[str, str] | None:
    with _control_state_lock:
        if _last_control is None:
            return None
        return dict(_last_control)


def _seconds_since(timestamp: str) -> float | None:
    try:
        started = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    return (datetime.now(KST) - started).total_seconds()


def _is_state_consistent(
    *,
    power: str,
    mode: str,
    auto_state: str | None,
    last_control: dict[str, str] | None,
    reconcile_grace_seconds: int,
) -> bool:
    expected_power = "off" if mode == "off" else "on"
    mode_power_consistent = power == expected_power

    auto_mode_consistent = True
    auto_power_consistent = True
    if auto_state in {"on", "off"}:
        expected_auto = "off" if mode == "off" else "on"
        auto_mode_consistent = auto_state == expected_auto
        auto_power_consistent = auto_state == power

    if mode_power_consistent and auto_mode_consistent and auto_power_consistent:
        return True

    if last_control is None:
        return False

    if last_control.get("result") != "success":
        return False

    elapsed = _seconds_since(last_control.get("at", ""))
    if elapsed is None or elapsed > reconcile_grace_seconds:
        return False

    return mode == last_control.get("mode")


def _raise_ac_http_error(
    *,
    request_id: str,
    detail: str,
    code: str,
    status_code: int = 502,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"detail": detail, "code": code},
        headers={"X-Request-ID": request_id},
    )


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
    auto_state = status.ac_auto_state.state if status.ac_auto_state is not None else None
    last_control = _read_last_control()
    state_consistent = _is_state_consistent(
        power=power,
        mode=mode,
        auto_state=auto_state,
        last_control=last_control,
        reconcile_grace_seconds=settings.ac_state_reconcile_grace_seconds,
    )
    temperature_c = status.indoor.temperature if status.indoor else None
    humidity = status.indoor.humidity if status.indoor else None

    return AcStateResponse(
        power=power,
        mode=mode,
        auto_enabled=auto_enabled,
        state_consistent=state_consistent,
        state_source=AC_STATE_SOURCE,
        last_control_at=last_control.get("at") if last_control else None,
        last_control_result=last_control.get("result") if last_control else None,
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
        _remember_control(body.mode, "failed")
        logger.error(
            "ac mode sync failed request_id=%s requested_mode=%s error=%s",
            request_id,
            body.mode,
            exc,
        )
        _raise_ac_http_error(
            request_id=request_id,
            detail="AC mode sync failed",
            code="ac_mode_sync_failed",
        )

    # Reflect manual control into HA last_on/off timestamps.
    try:
        entity_id = ENTITY_AC_LAST_ON if body.mode != "off" else ENTITY_AC_LAST_OFF
        await ha.call_service(
            "input_datetime",
            "set_datetime",
            {"entity_id": entity_id, "datetime": _now_kst_input_datetime()},
        )
    except Exception as exc:
        _remember_control(body.mode, "failed")
        logger.error(
            "ac last_on_off sync failed request_id=%s requested_mode=%s error=%s",
            request_id,
            body.mode,
            exc,
        )
        _raise_ac_http_error(
            request_id=request_id,
            detail="AC timestamp sync failed",
            code="ac_timestamp_sync_failed",
        )

    # Re-fetch to verify response consistency for frontend state update.
    status = await fetch_status(settings)
    raw_mode = await ha.get_state(ENTITY_AC_MODE)
    applied_mode = str(raw_mode.get("state") or "").strip().lower()
    if applied_mode not in {"off", "cool", "dry"}:
        _remember_control(body.mode, "failed")
        logger.error(
            "ac verify failed invalid mode request_id=%s requested_mode=%s applied_mode=%s",
            request_id,
            body.mode,
            applied_mode,
        )
        _raise_ac_http_error(
            request_id=request_id,
            detail="AC verify failed",
            code="ac_verify_failed",
        )

    if applied_mode != body.mode:
        _remember_control(body.mode, "failed")
        logger.error(
            "ac verify mismatch request_id=%s requested_mode=%s applied_mode=%s",
            request_id,
            body.mode,
            applied_mode,
        )
        _raise_ac_http_error(
            request_id=request_id,
            detail="AC state mismatch after control",
            code="ac_state_mismatch",
        )

    _remember_control(applied_mode, "success")
    power = "on" if status.ac_estimated_running else "off"
    return AcActionResponse(
        request_id=request_id,
        applied_mode=applied_mode,
        power=power,
    )
