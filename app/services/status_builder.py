from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.config import Settings
from app.constants import (
    ENTITY_INDOOR_HUMIDITY,
    ENTITY_INDOOR_TEMP,
    ENTITY_AC_AUTO_ENABLED,
    ENTITY_AC_AUTO_STATE,
    ENTITY_AC_AWAY_ENABLED,
    ENTITY_AC_LAST_RUN_MODE,
    ENTITY_AC_MODE,
    ENTITY_PC_CLOUD,
    ENTITY_PC_ENERGY_MONTH,
    ENTITY_PC_ENERGY_TODAY,
    ENTITY_PC_OVERLOAD,
    ENTITY_PC_POWER,
    ENTITY_PC_SIGNAL,
    ENTITY_PC_SWITCH,
    ENTITY_PLUG_ENERGY,
    ENTITY_PLUG_POWER,
    ENTITY_PLUG_SWITCH,
    ENTITY_WEATHER,
    STATUS_ENTITY_IDS,
)
from app.models.schemas import (
    AcAutoState,
    AcLastRunMode,
    AcMode,
    AcOperatingMode,
    ElectricityInfo,
    IndoorClimate,
    PcStatus,
    PlugStatus,
    StatusResponse,
    WeatherOutdoor,
)
from app.services.ha_client import HAClient

KST = ZoneInfo("Asia/Seoul")
SwitchState = Literal["on", "off", "unavailable", "unknown"]
AcPowerSource = Literal["plug", "logical"]
AcPowerDisplay = Literal["on", "off"]
AC_MODES: frozenset[str] = frozenset({"off", "auto", "cool", "dry"})
AC_LAST_RUN_MODES: frozenset[str] = frozenset({"cool", "dry"})


def _now_kst_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower()
    if s in ("unavailable", "unknown", "none", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _switch_state(state: str | None) -> SwitchState:
    if state in ("on", "off"):
        return state
    if state == "unavailable":
        return "unavailable"
    return "unknown"


def _binary_is_on(state: str | None) -> bool:
    return str(state or "").strip().lower() == "on"


def _parse_int(value: Any) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _estimate_cost_won(kwh: float | None, rate_won_per_kwh: float) -> int | None:
    if kwh is None:
        return None
    return int(round(kwh * rate_won_per_kwh, 0))


def _entity_state_unusable(state: str | None) -> bool:
    if state is None:
        return True
    return str(state).strip().lower() in ("unavailable", "unknown", "none", "")


def _fahrenheit_to_celsius(fahrenheit: float) -> float:
    return round((fahrenheit - 32) * 5 / 9, 1)


def _temperature_celsius(raw: dict[str, Any]) -> float | None:
    value = _parse_float(raw.get("state"))
    if value is None:
        return None
    unit = str((raw.get("attributes") or {}).get("unit_of_measurement", "")).strip().upper()
    if unit in ("°C", "C"):
        return round(value, 1)
    return _fahrenheit_to_celsius(value)


def _build_indoor(states: dict[str, dict[str, Any]]) -> IndoorClimate | None:
    temp_raw = states.get(ENTITY_INDOOR_TEMP)
    humidity_raw = states.get(ENTITY_INDOOR_HUMIDITY)
    if not temp_raw or not humidity_raw:
        return None
    if _entity_state_unusable(temp_raw.get("state")) or _entity_state_unusable(
        humidity_raw.get("state")
    ):
        return None
    temperature = _temperature_celsius(temp_raw)
    humidity = _parse_float(humidity_raw.get("state"))
    if temperature is None or humidity is None:
        return None
    return IndoorClimate(temperature=temperature, humidity=humidity)


def _build_pc(
    states: dict[str, dict[str, Any]],
    *,
    pc_power_threshold_w: float,
    estimate_rate_won_per_kwh: float,
) -> PcStatus:
    switch_raw = states.get(ENTITY_PC_SWITCH, {})
    power_raw = states.get(ENTITY_PC_POWER, {})
    energy_today_raw = states.get(ENTITY_PC_ENERGY_TODAY, {})
    energy_month_raw = states.get(ENTITY_PC_ENERGY_MONTH, {})
    cloud_raw = states.get(ENTITY_PC_CLOUD, {})
    signal_raw = states.get(ENTITY_PC_SIGNAL, {})
    overload_raw = states.get(ENTITY_PC_OVERLOAD, {})

    switch = _switch_state(switch_raw.get("state"))
    power_w = _parse_float(power_raw.get("state"))
    energy_today_kwh = _parse_float(energy_today_raw.get("state"))
    energy_month_kwh = _parse_float(energy_month_raw.get("state"))
    estimated_running = power_w is not None and power_w >= pc_power_threshold_w

    return PcStatus(
        switch=switch,
        power_w=power_w,
        energy_today_kwh=energy_today_kwh,
        energy_month_kwh=energy_month_kwh,
        estimated_cost_today_won=_estimate_cost_won(energy_today_kwh, estimate_rate_won_per_kwh),
        estimated_cost_month_won=_estimate_cost_won(energy_month_kwh, estimate_rate_won_per_kwh),
        online=_binary_is_on(cloud_raw.get("state")),
        wifi_signal_level=_parse_int(signal_raw.get("state")),
        overload=_binary_is_on(overload_raw.get("state")),
        estimated_running=estimated_running,
    )


def _ac_auto_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if s.lower() in ("unknown", "unavailable", "none", ""):
        return None
    return s


def _build_ac_auto_enabled(states: dict[str, dict[str, Any]]) -> bool | None:
    raw = states.get(ENTITY_AC_AUTO_ENABLED)
    if not raw:
        return None
    state = str(raw.get("state") or "").strip().lower()
    if state == "on":
        return True
    if state == "off":
        return False
    return None


def _build_ac_away_enabled(states: dict[str, dict[str, Any]]) -> bool | None:
    raw = states.get(ENTITY_AC_AWAY_ENABLED)
    if not raw:
        return None
    state = str(raw.get("state") or "").strip().lower()
    if state == "on":
        return True
    if state == "off":
        return False
    return None


def derive_ac_operating_mode(
    *,
    auto_enabled: bool | None,
    away_enabled: bool | None,
) -> AcOperatingMode | None:
    if away_enabled is True:
        return "away"
    if auto_enabled is True:
        return "auto"
    if away_enabled is False and auto_enabled is not True:
        return "manual"
    if auto_enabled is False and away_enabled is not True:
        return "manual"
    return None


def resolve_ha_ac_mode(
    *,
    mode: AcMode,
    operating_mode: AcOperatingMode | None = None,
    auto_toggle: bool | None = None,
    away_toggle: bool | None = None,
) -> AcMode:
    """Map API request ``mode`` to HA ``input_select`` value.

    ``operating_mode`` / mutex toggles are applied separately; they must not
    override a physical ``mode=off`` (turn_off script + ``input_select=off``).
    """
    return mode


def is_ac_automation_blocked(
    *,
    mode: AcMode,
    auto_enabled: bool | None,
    away_enabled: bool | None,
) -> bool:
    """``auto_enabled``/``away_enabled`` ON while ``input_select=off`` blocks HA automations."""
    if mode != "off":
        return False
    return auto_enabled is True or away_enabled is True


def resolve_ac_mutex_toggles(
    *,
    auto_enabled: bool | None = None,
    away_enabled: bool | None = None,
    operating_mode: AcOperatingMode | None = None,
) -> tuple[bool | None, bool | None]:
    if operating_mode == "manual":
        return False, False
    if operating_mode == "auto":
        return True, False
    if operating_mode == "away":
        return False, True

    auto = auto_enabled
    away = away_enabled
    if auto is True and away is True:
        auto = False
    elif auto is True:
        away = False
    elif away is True:
        auto = False
    return auto, away


def parse_ac_mode(raw: dict[str, Any] | None) -> AcMode:
    if not raw:
        return "off"
    state = str(raw.get("state") or "").strip().lower()
    if state in AC_MODES:
        return state  # type: ignore[return-value]
    return "off"


def parse_ac_last_run_mode(value: Any) -> AcLastRunMode | None:
    s = str(value or "").strip().lower()
    if s in AC_LAST_RUN_MODES:
        return s  # type: ignore[return-value]
    return None


def _build_ac_mode(states: dict[str, dict[str, Any]]) -> AcMode:
    return parse_ac_mode(states.get(ENTITY_AC_MODE))


def _build_ac_last_run_mode(states: dict[str, dict[str, Any]]) -> AcLastRunMode | None:
    raw = states.get(ENTITY_AC_LAST_RUN_MODE)
    if raw is not None:
        return parse_ac_last_run_mode(raw.get("state"))
    auto_raw = states.get(ENTITY_AC_AUTO_STATE)
    if auto_raw:
        attrs = auto_raw.get("attributes") or {}
        return parse_ac_last_run_mode(attrs.get("last_run_mode"))
    return None


def ac_plug_running(power_w: float | None, *, ac_power_threshold_w: float) -> bool:
    return power_w is not None and power_w >= ac_power_threshold_w


def ac_logical_running(ac_auto_state: AcAutoState | None) -> bool:
    return ac_auto_state is not None and ac_auto_state.state == "on"


def ac_composite_running(
    power_w: float | None,
    *,
    ac_power_threshold_w: float,
    ac_auto_state: AcAutoState | None,
) -> bool:
    return ac_plug_running(power_w, ac_power_threshold_w=ac_power_threshold_w) or ac_logical_running(
        ac_auto_state
    )


def resolve_ac_power(
    power_w: float | None,
    *,
    ac_power_threshold_w: float,
    ac_auto_state: AcAutoState | None,
) -> tuple[AcPowerDisplay, AcPowerSource]:
    if ac_plug_running(power_w, ac_power_threshold_w=ac_power_threshold_w):
        return "on", "plug"
    if ac_logical_running(ac_auto_state):
        return "on", "logical"
    return "off", "plug"


def _build_ac_auto_state(
    states: dict[str, dict[str, Any]],
    *,
    last_run_mode: AcLastRunMode | None = None,
) -> AcAutoState | None:
    raw = states.get(ENTITY_AC_AUTO_STATE)
    if not raw:
        return None
    state = str(raw.get("state") or "").strip().lower()
    if state not in ("on", "off", "unknown", "unavailable"):
        state = "unknown"
    attrs = raw.get("attributes") or {}
    mirrored_last_run_mode = parse_ac_last_run_mode(attrs.get("last_run_mode"))
    return AcAutoState(
        state=state,  # type: ignore[arg-type]
        last_on=_ac_auto_timestamp(attrs.get("last_on")),
        last_off=_ac_auto_timestamp(attrs.get("last_off")),
        last_transition=_ac_auto_timestamp(attrs.get("last_transition")),
        last_run_mode=last_run_mode if last_run_mode is not None else mirrored_last_run_mode,
    )


def build_status_from_states(
    states: dict[str, dict[str, Any]],
    *,
    ac_power_threshold_w: float,
    pc_power_threshold_w: float,
    estimate_rate_won_per_kwh: float,
) -> StatusResponse:
    plug_switch_raw = states.get(ENTITY_PLUG_SWITCH, {})
    plug_power_raw = states.get(ENTITY_PLUG_POWER, {})
    plug_energy_raw = states.get(ENTITY_PLUG_ENERGY, {})
    weather_raw = states.get(ENTITY_WEATHER, {})

    switch = _switch_state(plug_switch_raw.get("state"))
    power_w = _parse_float(plug_power_raw.get("state"))
    energy_kwh = _parse_float(plug_energy_raw.get("state"))

    ac_auto_enabled = _build_ac_auto_enabled(states)
    ac_away_enabled = _build_ac_away_enabled(states)
    ac_auto_state = _build_ac_auto_state(states, last_run_mode=_build_ac_last_run_mode(states))
    ac_running = ac_composite_running(
        power_w,
        ac_power_threshold_w=ac_power_threshold_w,
        ac_auto_state=ac_auto_state,
    )

    weather_attrs = weather_raw.get("attributes") or {}
    weather: WeatherOutdoor | None = None
    if weather_raw:
        weather = WeatherOutdoor(
            temperature=_parse_float(weather_attrs.get("temperature")),
            humidity=weather_attrs.get("humidity"),
            condition=weather_attrs.get("condition") or weather_raw.get("state"),
        )

    return StatusResponse(
        plug=PlugStatus(
            switch=switch,
            power_w=power_w,
            energy_kwh=energy_kwh,
            estimated_cost_won=_estimate_cost_won(energy_kwh, estimate_rate_won_per_kwh),
        ),
        pc=_build_pc(
            states,
            pc_power_threshold_w=pc_power_threshold_w,
            estimate_rate_won_per_kwh=estimate_rate_won_per_kwh,
        ),
        electricity=ElectricityInfo(rate_won_per_kwh=estimate_rate_won_per_kwh),
        ac_estimated_running=ac_running,
        ac_auto_enabled=ac_auto_enabled,
        ac_away_enabled=ac_away_enabled,
        ac_operating_mode=derive_ac_operating_mode(
            auto_enabled=ac_auto_enabled,
            away_enabled=ac_away_enabled,
        ),
        ac_mode=_build_ac_mode(states),
        ac_last_run_mode=_build_ac_last_run_mode(states),
        ac_auto_state=ac_auto_state,
        indoor=_build_indoor(states),
        weather_outdoor=weather,
        updated_at=_now_kst_iso(),
    )


async def fetch_and_build_status(ha: HAClient, settings: Settings) -> StatusResponse:
    states = await ha.get_states_for(STATUS_ENTITY_IDS)
    return build_status_from_states(
        states,
        ac_power_threshold_w=settings.ac_power_threshold_w,
        pc_power_threshold_w=settings.pc_power_threshold_w,
        estimate_rate_won_per_kwh=settings.estimate_rate_won_per_kwh,
    )
