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
    ENTITY_AC_AWAY_ENABLED,
    ENTITY_AC_AUTO_ENABLED,
    ENTITY_AC_LAST_OFF,
    ENTITY_AC_LAST_ON,
    ENTITY_AC_MODE,
    ENTITY_AC_REMOTE,
    ENTITY_PLUG_SWITCH,
)
from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import (
    AcActionRequest,
    AcActionResponse,
    AcAutoToggleRequest,
    AcAutoToggleResponse,
    AcMode,
    AcStateResponse,
    AcThresholdRule,
    AcThresholdsResponse,
)
from app.services.ha_client import HAClient
from app.services.status_service import fetch_status
from app.services.status_builder import (
    AC_MODES,
    _switch_state,
    derive_ac_operating_mode,
    resolve_ac_mutex_toggles,
    resolve_ac_power,
)

router = APIRouter(prefix="/api/v1", tags=["ac"])
logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
AC_STATE_SOURCE = "composed(plug_w,ac_auto_state,ha_input_select)"
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
    if mode == "off":
        expected_power = "off"
    elif mode == "auto":
        expected_power = "on" if auto_state == "on" else "off"
    else:
        expected_power = "on"
    mode_power_consistent = power == expected_power

    auto_mode_consistent = True
    auto_power_consistent = True
    if auto_state in {"on", "off"}:
        if mode == "off":
            auto_mode_consistent = auto_state == "off"
            auto_power_consistent = auto_state == power
        elif mode == "auto":
            auto_power_consistent = auto_state == power
        else:
            auto_mode_consistent = auto_state == "on"
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


async def _sync_ac_mode_select(ha: HAClient, mode: AcMode) -> None:
    await ha.call_service(
        "input_select",
        "select_option",
        {"entity_id": ENTITY_AC_MODE, "option": mode},
    )


async def _sync_ac_last_on_off(ha: HAClient, mode: AcMode) -> None:
    entity_id = ENTITY_AC_LAST_ON if mode != "off" else ENTITY_AC_LAST_OFF
    await ha.call_service(
        "input_datetime",
        "set_datetime",
        {"entity_id": entity_id, "datetime": _now_kst_input_datetime()},
    )


async def _toggle_ac_away(ha: HAClient, enabled: bool) -> None:
    service = "turn_on" if enabled else "turn_off"
    await ha.call_service(
        "input_boolean",
        service,
        {"entity_id": ENTITY_AC_AWAY_ENABLED},
    )


async def _toggle_ac_auto_enabled(
    ha: HAClient,
    *,
    enabled: bool,
    request_id: str,
) -> Literal["on", "off", "unavailable", "unknown"]:
    auto_service = "turn_on" if enabled else "turn_off"
    await ha.call_service(
        "input_boolean",
        auto_service,
        {"entity_id": ENTITY_AC_AUTO_ENABLED},
    )

    if enabled:
        try:
            await ha.call_service(
                "switch",
                "turn_on",
                {"entity_id": ENTITY_PLUG_SWITCH},
            )
        except Exception as exc:
            logger.error(
                "ac auto plug sync failed request_id=%s enabled=%s error=%s",
                request_id,
                enabled,
                exc,
            )
            _raise_ac_http_error(
                request_id=request_id,
                detail="AC auto toggle succeeded but plug sync failed",
                code="ac_auto_plug_sync_failed",
            )

        plug_state = await ha.get_state(ENTITY_PLUG_SWITCH)
        switch = _switch_state(plug_state.get("state"))
        if switch != "on":
            logger.error(
                "ac auto verify mismatch request_id=%s enabled=%s plug_switch=%s",
                request_id,
                enabled,
                switch,
            )
            _raise_ac_http_error(
                request_id=request_id,
                detail="AC auto toggle succeeded but plug state mismatch",
                code="ac_auto_plug_state_mismatch",
            )
        return switch

    plug_state = await ha.get_state(ENTITY_PLUG_SWITCH)
    return _switch_state(plug_state.get("state"))


@router.get(
    "/ac/thresholds",
    response_model=AcThresholdsResponse,
    summary="에어컨 자동/외출 임계값 v2.1 (HA automation 정본)",
)
async def get_ac_thresholds(_key: ApiKeyDep) -> AcThresholdsResponse:
    return AcThresholdsResponse(
        version="v2.1",
        home_auto=AcThresholdRule(
            on="실내 ≥25°C(5분, OFF 후 재가동) 또는 습≥60%(10분); 습 스냅 ≥65% 즉시 ON",
            off="온도: <25°C·습<55%(10분); 습 스냅: <50%·<25°C 즉시 OFF",
            notes="자동 모드(input_boolean.hwiya_ac_auto_enabled ON) 시 HA automation v2.1 적용",
        ),
        away=AcThresholdRule(
            on="실내 ≥27°C 또는 습≥60%(10분)",
            off="실내 <27°C 및 습<60%",
            notes="외출 모드(input_boolean.hwiya_ac_away_enabled ON) 시 HA automation 적용",
        ),
    )


@router.get("/ac/state", response_model=AcStateResponse)
async def get_ac_state(
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> AcStateResponse:
    status = await fetch_status(settings)

    mode = status.ac_mode
    power, running_source = resolve_ac_power(
        status.plug.power_w,
        ac_power_threshold_w=settings.ac_power_threshold_w,
        ac_auto_state=status.ac_auto_state,
    )
    auto_enabled = bool(status.ac_auto_enabled)
    away_enabled = bool(status.ac_away_enabled)
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
        running_source=running_source,
        mode=mode,
        auto_enabled=auto_enabled,
        away_enabled=away_enabled,
        operating_mode=derive_ac_operating_mode(
            auto_enabled=status.ac_auto_enabled,
            away_enabled=status.ac_away_enabled,
        ),
        last_run_mode=status.ac_last_run_mode,
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

    ha = HAClient(settings)

    auto_toggle, away_toggle = resolve_ac_mutex_toggles(
        auto_enabled=body.auto_enabled,
        away_enabled=body.away_enabled,
        operating_mode=body.operating_mode,
    )

    if body.mode != "auto":
        if body.mode == "off":
            command = AC_COMMAND_OFF
        elif body.mode == "cool":
            command = AC_COMMAND_COOL_PRESET_17
        else:
            command = AC_COMMAND_DRY_PRESET_17

        await ha.call_service(
            "remote",
            "send_command",
            {
                "entity_id": ENTITY_AC_REMOTE,
                "device": AC_REMOTE_DEVICE,
                "command": command,
            },
        )

    try:
        await _sync_ac_mode_select(ha, body.mode)
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

    if body.mode in {"cool", "dry", "off"}:
        try:
            await _sync_ac_last_on_off(ha, body.mode)
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

    if away_toggle is not None:
        try:
            await _toggle_ac_away(ha, away_toggle)
        except Exception as exc:
            _remember_control(body.mode, "failed")
            logger.error(
                "ac away toggle failed request_id=%s away_enabled=%s error=%s",
                request_id,
                away_toggle,
                exc,
            )
            _raise_ac_http_error(
                request_id=request_id,
                detail="AC away toggle failed",
                code="ac_away_toggle_failed",
            )

    if auto_toggle is not None:
        try:
            await _toggle_ac_auto_enabled(
                ha,
                enabled=auto_toggle,
                request_id=request_id,
            )
        except HTTPException:
            raise
        except Exception as exc:
            _remember_control(body.mode, "failed")
            logger.error(
                "ac auto toggle failed request_id=%s auto_enabled=%s error=%s",
                request_id,
                auto_toggle,
                exc,
            )
            _raise_ac_http_error(
                request_id=request_id,
                detail="AC auto toggle failed",
                code="ac_auto_toggle_failed",
            )

    status = await fetch_status(settings)
    raw_mode = await ha.get_state(ENTITY_AC_MODE)
    applied_mode = str(raw_mode.get("state") or "").strip().lower()
    if applied_mode not in AC_MODES:
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
    power, _ = resolve_ac_power(
        status.plug.power_w,
        ac_power_threshold_w=settings.ac_power_threshold_w,
        ac_auto_state=status.ac_auto_state,
    )
    toggled_mutex = (
        body.operating_mode is not None
        or body.auto_enabled is not None
        or body.away_enabled is not None
    )
    return AcActionResponse(
        request_id=request_id,
        applied_mode=applied_mode,  # type: ignore[arg-type]
        power=power,
        auto_enabled=status.ac_auto_enabled if toggled_mutex else None,
        away_enabled=status.ac_away_enabled if toggled_mutex else None,
        operating_mode=(
            derive_ac_operating_mode(
                auto_enabled=status.ac_auto_enabled,
                away_enabled=status.ac_away_enabled,
            )
            if toggled_mutex
            else None
        ),
    )


@router.post("/ac/auto", response_model=AcAutoToggleResponse)
async def set_ac_auto(
    body: AcAutoToggleRequest,
    _key: ApiKeyDep,
    settings: SettingsDep,
    response: Response,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> AcAutoToggleResponse:
    request_id = x_request_id or str(uuid4())
    response.headers["X-Request-ID"] = request_id

    ha = HAClient(settings)
    auto_toggle, away_toggle = resolve_ac_mutex_toggles(auto_enabled=body.enabled)
    try:
        if away_toggle is not None:
            await _toggle_ac_away(ha, away_toggle)
        switch = await _toggle_ac_auto_enabled(
            ha,
            enabled=auto_toggle if auto_toggle is not None else body.enabled,
            request_id=request_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "ac auto toggle failed request_id=%s enabled=%s error=%s",
            request_id,
            body.enabled,
            exc,
        )
        _raise_ac_http_error(
            request_id=request_id,
            detail="AC auto toggle failed",
            code="ac_auto_toggle_failed",
        )

    return AcAutoToggleResponse(
        request_id=request_id,
        auto_enabled=body.enabled,
        plug_switch=switch,
    )
