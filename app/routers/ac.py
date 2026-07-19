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
    AC_REMOTE_DEVICE,
    ENTITY_AC_AWAY_ENABLED,
    ENTITY_AC_AUTO_ENABLED,
    ENTITY_AC_LAST_OFF,
    ENTITY_AC_LAST_ON,
    ENTITY_AC_MODE,
    ENTITY_AC_PLUG_CUT_SAFE,
    ENTITY_AC_REMOTE,
    ENTITY_AC_SCRIPT_MANUAL_TURN_OFF,
    ENTITY_AC_SCRIPT_SMART_ON,
    ENTITY_AC_SCRIPT_TURN_OFF,
    ENTITY_AC_SOFT_OFF,
    ENTITY_PLUG_POWER,
    ENTITY_PLUG_SWITCH,
)
from app.deps import ApiKeyDep, SettingsDep
from app.models.schemas import (
    AcActionRequest,
    AcActionResponse,
    AcAutoToggleRequest,
    AcAutoToggleResponse,
    AcMode,
    AcOperatingMode,
    AcRecoverRequest,
    AcRecoverResponse,
    AcStateResponse,
    AcThresholdRule,
    AcThresholdsResponse,
)
from app.services.ha_client import HAClient
from app.services.status_service import fetch_status
from app.services.status_builder import (
    AC_MODES,
    _switch_state,
    ac_composite_running,
    derive_ac_operating_mode,
    is_ac_automation_blocked,
    resolve_ac_mutex_toggles,
    resolve_ac_power,
    resolve_ac_running_confidence,
    resolve_ha_ac_mode,
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
    auto_enabled: bool,
    away_enabled: bool,
    last_control: dict[str, str] | None,
    reconcile_grace_seconds: int,
) -> bool:
    if is_ac_automation_blocked(
        mode=mode,  # type: ignore[arg-type]
        auto_enabled=auto_enabled,
        away_enabled=away_enabled,
    ):
        return False

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


def _ac_is_running_from_status(status: object, *, ac_power_threshold_w: float) -> bool:
    plug = getattr(status, "plug", None)
    power_w = getattr(plug, "power_w", None) if plug is not None else None
    power_stale = bool(getattr(plug, "power_stale", False)) if plug is not None else False
    ac_auto_state = getattr(status, "ac_auto_state", None)
    return ac_composite_running(
        power_w,
        ac_power_threshold_w=ac_power_threshold_w,
        ac_auto_state=ac_auto_state,
        power_stale=power_stale,
    )


def _should_invoke_smart_on(
    *,
    mode: AcMode,
    was_running: bool,
    auto_toggle: bool | None,
    operating_mode: AcOperatingMode | None,
    auto_enabled: bool | None,
    status_auto_enabled: bool | None,
) -> bool:
    if mode != "auto" or was_running:
        return False
    if auto_toggle is True or operating_mode == "auto" or auto_enabled is True:
        return True
    if auto_toggle is not False and auto_enabled is not False and status_auto_enabled:
        return True
    return False


async def _invoke_ac_smart_on(ha: HAClient) -> None:
    await ha.call_service(
        "script",
        "turn_on",
        {
            "entity_id": ENTITY_AC_SCRIPT_SMART_ON,
            "variables": {"reason": "temp"},
        },
    )


async def _invoke_ac_turn_off_script(ha: HAClient) -> None:
    await ha.call_service(
        "script",
        "turn_on",
        {"entity_id": ENTITY_AC_SCRIPT_TURN_OFF},
    )


async def _invoke_ac_manual_turn_off(ha: HAClient) -> None:
    """수동/PWA OFF — 온도·가동 조건 없는 IR ac_off (자동용 turn_off 스크립트와 분리)."""
    await ha.call_service(
        "script",
        "turn_on",
        {"entity_id": ENTITY_AC_SCRIPT_MANUAL_TURN_OFF},
    )


async def _ensure_plug_on_for_ir(ha: HAClient, *, request_id: str) -> None:
    """IR 송신 전 — 콘센트가 명시적으로 OFF일 때만 ON. (unknown이면 강제하지 않음)"""
    plug_state = await ha.get_state(ENTITY_PLUG_SWITCH)
    switch = _switch_state(plug_state.get("state"))
    if switch == "on":
        return
    if switch != "off":
        logger.warning(
            "ac plug ensure skip request_id=%s plug_switch=%s",
            request_id,
            switch,
        )
        return
    try:
        await ha.call_service(
            "switch",
            "turn_on",
            {"entity_id": ENTITY_PLUG_SWITCH},
        )
    except Exception as exc:
        logger.error(
            "ac plug ensure-on failed request_id=%s error=%s",
            request_id,
            exc,
        )
        _raise_ac_http_error(
            request_id=request_id,
            detail="AC plug must be on before IR; plug turn_on failed",
            code="ac_plug_ensure_failed",
        )


async def _ha_bool_on(ha: HAClient, entity_id: str) -> bool | None:
    raw = await ha.get_state(entity_id)
    state = str(raw.get("state") or "").strip().lower()
    if state in {"on", "true"}:
        return True
    if state in {"off", "false"}:
        return False
    return None


async def _read_soft_off_flags(ha: HAClient, *, ac_power_threshold_w: float) -> tuple[bool, bool]:
    """soft-off/plug_cut_safe HA 이진 센서 우선, 미기동 시 전력으로 폴백."""
    soft = await _ha_bool_on(ha, ENTITY_AC_SOFT_OFF)
    cut = await _ha_bool_on(ha, ENTITY_AC_PLUG_CUT_SAFE)
    if soft is not None and cut is not None:
        return soft, cut
    power_raw = await ha.get_state(ENTITY_PLUG_POWER)
    try:
        power_w = float(power_raw.get("state"))
    except (TypeError, ValueError):
        return False, False
    soft_off = power_w < ac_power_threshold_w
    plug_state = await ha.get_state(ENTITY_PLUG_SWITCH)
    switch = _switch_state(plug_state.get("state"))
    plug_cut_safe = switch != "on" or soft_off
    return soft_off, plug_cut_safe


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


_SMART_ON_NOTE = "스마트 ON(모드 auto): ≥27°C 냉방, 26~26.5°C 제습, <26°C OFF"


@router.get(
    "/ac/thresholds",
    response_model=AcThresholdsResponse,
    summary="에어컨 자동/외출 임계값 v4.0 (HA automation 정본)",
)
async def get_ac_thresholds(_key: ApiKeyDep) -> AcThresholdsResponse:
    return AcThresholdsResponse(
        version="v4.0",
        home_auto=AcThresholdRule(
            on=(
                "실내 ≥27°C 냉방 ON; 26~26.5°C 제습; 가동 판정 ≥15W; "
                f"{_SMART_ON_NOTE}"
            ),
            off="실내 <26°C OFF",
            notes=(
                "자동 모드(input_boolean.hwiya_ac_auto_enabled ON) 시 HA automation v4.0 적용; "
                "input_select=off일 때만 auto·away OFF(cool/dry 시 auto 유지); "
                "수동 cool/dry: 스마트 ON만 해당(센서 자동 ON/OFF 미적용); "
                "플러그 전력 신선도(power_stale) 참고"
            ),
        ),
        away=AcThresholdRule(
            on=(
                "실내 ≥28°C 즉시 ON; "
                f"{_SMART_ON_NOTE}"
            ),
            off="실내 <28°C OFF",
            notes=(
                "외출 모드(input_boolean.hwiya_ac_away_enabled ON) 시 HA automation v4.0 적용; "
                "input_select=off일 때만 auto·away OFF(cool/dry 시 auto 유지); "
                "수동 cool/dry: 스마트 ON만 해당"
            ),
        ),
        mutex=(
            "input_select=off 시만 input_boolean auto·away OFF; "
            "cool/dry 선택 시 hwiya_ac_auto_enabled 유지 — HA automation v4.0"
        ),
    )


@router.get("/ac/state", response_model=AcStateResponse)
async def get_ac_state(
    _key: ApiKeyDep,
    settings: SettingsDep,
) -> AcStateResponse:
    status = await fetch_status(settings)

    mode = status.ac_mode
    power_stale = bool(getattr(status.plug, "power_stale", False))
    power, running_source = resolve_ac_power(
        status.plug.power_w,
        ac_power_threshold_w=settings.ac_power_threshold_w,
        ac_auto_state=status.ac_auto_state,
        power_stale=power_stale,
    )
    auto_enabled = bool(status.ac_auto_enabled)
    away_enabled = bool(status.ac_away_enabled)
    auto_state = status.ac_auto_state.state if status.ac_auto_state is not None else None
    last_control = _read_last_control()
    state_consistent = _is_state_consistent(
        power=power,
        mode=mode,
        auto_state=auto_state,
        auto_enabled=auto_enabled,
        away_enabled=away_enabled,
        last_control=last_control,
        reconcile_grace_seconds=settings.ac_state_reconcile_grace_seconds,
    )
    temperature_c = status.indoor.temperature if status.indoor else None
    humidity = status.indoor.humidity if status.indoor else None
    ac_running_confidence = getattr(status, "ac_running_confidence", None)
    if ac_running_confidence not in {"high", "medium", "low"}:
        ac_running_confidence = resolve_ac_running_confidence(
            power_stale=power_stale,
            running_source=running_source,
            power=power,
        )

    ha = HAClient(settings)
    soft_off, plug_cut_safe = await _read_soft_off_flags(
        ha,
        ac_power_threshold_w=settings.ac_power_threshold_w,
    )

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
        power_updated_at=getattr(status.plug, "power_updated_at", None),
        power_age_seconds=getattr(status.plug, "power_age_seconds", None),
        power_stale=power_stale,
        ac_running_confidence=ac_running_confidence,
        soft_off=soft_off,
        plug_cut_safe=plug_cut_safe,
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
    ha_mode = resolve_ha_ac_mode(
        mode=body.mode,
        operating_mode=body.operating_mode,
        auto_toggle=auto_toggle,
        away_toggle=away_toggle,
    )

    initial_status = await fetch_status(settings)
    was_running = _ac_is_running_from_status(
        initial_status,
        ac_power_threshold_w=settings.ac_power_threshold_w,
    )

    try:
        if body.mode == "off" and ha_mode == "off":
            await _ensure_plug_on_for_ir(ha, request_id=request_id)
            await _invoke_ac_manual_turn_off(ha)
        elif body.mode == "cool":
            await _ensure_plug_on_for_ir(ha, request_id=request_id)
            await ha.call_service(
                "remote",
                "send_command",
                {
                    "entity_id": ENTITY_AC_REMOTE,
                    "device": AC_REMOTE_DEVICE,
                    "command": AC_COMMAND_COOL_PRESET_17,
                },
            )
        elif body.mode == "dry":
            await _ensure_plug_on_for_ir(ha, request_id=request_id)
            await ha.call_service(
                "remote",
                "send_command",
                {
                    "entity_id": ENTITY_AC_REMOTE,
                    "device": AC_REMOTE_DEVICE,
                    "command": AC_COMMAND_DRY_PRESET_17,
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        _remember_control(ha_mode, "failed")
        logger.error(
            "ac primary control failed request_id=%s requested_mode=%s ha_mode=%s error=%s",
            request_id,
            body.mode,
            ha_mode,
            exc,
        )
        _raise_ac_http_error(
            request_id=request_id,
            detail="AC control failed",
            code="ac_control_failed",
        )

    try:
        await _sync_ac_mode_select(ha, ha_mode)
    except Exception as exc:
        _remember_control(ha_mode, "failed")
        logger.error(
            "ac mode sync failed request_id=%s requested_mode=%s ha_mode=%s error=%s",
            request_id,
            body.mode,
            ha_mode,
            exc,
        )
        _raise_ac_http_error(
            request_id=request_id,
            detail="AC mode sync failed",
            code="ac_mode_sync_failed",
        )

    if ha_mode in {"cool", "dry"}:
        try:
            await _sync_ac_last_on_off(ha, ha_mode)
        except Exception as exc:
            _remember_control(ha_mode, "failed")
            logger.error(
                "ac last_on_off sync failed request_id=%s ha_mode=%s error=%s",
                request_id,
                ha_mode,
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
            _remember_control(ha_mode, "failed")
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
            _remember_control(ha_mode, "failed")
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

    if _should_invoke_smart_on(
        mode=ha_mode,
        was_running=was_running,
        auto_toggle=auto_toggle,
        operating_mode=body.operating_mode,
        auto_enabled=body.auto_enabled,
        status_auto_enabled=initial_status.ac_auto_enabled,
    ):
        try:
            await _ensure_plug_on_for_ir(ha, request_id=request_id)
            await _invoke_ac_smart_on(ha)
        except HTTPException:
            raise
        except Exception as exc:
            _remember_control(ha_mode, "failed")
            logger.error(
                "ac smart_on failed request_id=%s error=%s",
                request_id,
                exc,
            )
            _raise_ac_http_error(
                request_id=request_id,
                detail="AC smart on failed",
                code="ac_smart_on_failed",
            )

    status = await fetch_status(settings)
    raw_mode = await ha.get_state(ENTITY_AC_MODE)
    applied_mode = str(raw_mode.get("state") or "").strip().lower()
    if applied_mode not in AC_MODES:
        _remember_control(ha_mode, "failed")
        logger.error(
            "ac verify failed invalid mode request_id=%s ha_mode=%s applied_mode=%s",
            request_id,
            ha_mode,
            applied_mode,
        )
        _raise_ac_http_error(
            request_id=request_id,
            detail="AC verify failed",
            code="ac_verify_failed",
        )

    if applied_mode != ha_mode:
        _remember_control(ha_mode, "failed")
        logger.error(
            "ac verify mismatch request_id=%s ha_mode=%s applied_mode=%s",
            request_id,
            ha_mode,
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
        power_stale=bool(getattr(status.plug, "power_stale", False)),
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
    initial_status = await fetch_status(settings)
    was_running = _ac_is_running_from_status(
        initial_status,
        ac_power_threshold_w=settings.ac_power_threshold_w,
    )
    try:
        if away_toggle is not None:
            await _toggle_ac_away(ha, away_toggle)
        switch = await _toggle_ac_auto_enabled(
            ha,
            enabled=auto_toggle if auto_toggle is not None else body.enabled,
            request_id=request_id,
        )
        if body.enabled:
            await _sync_ac_mode_select(ha, "auto")
        if body.enabled and not was_running:
            await _invoke_ac_smart_on(ha)
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


@router.post("/ac/recover", response_model=AcRecoverResponse)
async def recover_ac(
    _key: ApiKeyDep,
    settings: SettingsDep,
    response: Response,
    body: AcRecoverRequest = AcRecoverRequest(),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> AcRecoverResponse:
    """IR/상태 자가진단 수동 복구. 콘센트 ON → IR 재송신 → soft_off 플래그 반환."""
    request_id = x_request_id or str(uuid4())
    response.headers["X-Request-ID"] = request_id
    force = body.force_ir or "auto"
    ha = HAClient(settings)
    steps: list[str] = []
    chosen = force

    try:
        await _ensure_plug_on_for_ir(ha, request_id=request_id)
        steps.append("plug_ensure_on")

        status = await fetch_status(settings)
        temp = status.indoor.temperature if status.indoor else None
        was_running = _ac_is_running_from_status(
            status,
            ac_power_threshold_w=settings.ac_power_threshold_w,
        )
        if force == "auto":
            t = temp if temp is not None else -99.0
            if was_running and t < 26.0:
                chosen = "off"
            elif not was_running and t >= 27.0:
                chosen = "cool"
            elif was_running and 26.0 <= t < 26.5:
                chosen = "dry"
            elif not was_running:
                chosen = "cool" if t >= 27.0 else "dry"
            else:
                chosen = "cool" if t >= 27.0 else ("dry" if t >= 26.0 else "off")

        if chosen == "off":
            await _invoke_ac_manual_turn_off(ha)
            steps.append("ir_manual_off")
        elif chosen == "dry":
            await ha.call_service(
                "remote",
                "send_command",
                {
                    "entity_id": ENTITY_AC_REMOTE,
                    "device": AC_REMOTE_DEVICE,
                    "command": AC_COMMAND_DRY_PRESET_17,
                },
            )
            steps.append("ir_dry")
        elif chosen == "smart":
            await _invoke_ac_smart_on(ha)
            steps.append("ir_smart_on")
        else:
            await ha.call_service(
                "remote",
                "send_command",
                {
                    "entity_id": ENTITY_AC_REMOTE,
                    "device": AC_REMOTE_DEVICE,
                    "command": AC_COMMAND_COOL_PRESET_17,
                },
            )
            steps.append("ir_cool")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("ac recover failed request_id=%s error=%s", request_id, exc)
        _raise_ac_http_error(
            request_id=request_id,
            detail="AC recover failed",
            code="ac_recover_failed",
        )

    soft_off, plug_cut_safe = await _read_soft_off_flags(
        ha,
        ac_power_threshold_w=settings.ac_power_threshold_w,
    )
    power_raw = await ha.get_state(ENTITY_PLUG_POWER)
    try:
        power_w = float(power_raw.get("state"))
    except (TypeError, ValueError):
        power_w = None

    return AcRecoverResponse(
        request_id=request_id,
        chosen_ir=chosen,
        steps=steps,
        soft_off=soft_off,
        plug_cut_safe=plug_cut_safe,
        power_w=power_w,
        detail="plug on + IR re-send; use soft_off/plug_cut_safe for plug OFF gate",
    )
