from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.config import Settings
from app.constants import (
    ENTITY_INDOOR_HUMIDITY,
    ENTITY_INDOOR_TEMP,
    ENTITY_PERSON,
    ENTITY_PLUG_ENERGY,
    ENTITY_PLUG_POWER,
    ENTITY_PLUG_SWITCH,
    ENTITY_WEATHER,
    STATUS_ENTITY_IDS,
)
from app.models.schemas import (
    IndoorClimate,
    PersonStatus,
    PlugStatus,
    StatusResponse,
    WeatherOutdoor,
)
from app.services.ha_client import HAClient

KST = ZoneInfo("Asia/Seoul")
SwitchState = Literal["on", "off", "unavailable", "unknown"]


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


def build_status_from_states(
    states: dict[str, dict[str, Any]],
    *,
    ac_power_threshold_w: float,
) -> StatusResponse:
    plug_switch_raw = states.get(ENTITY_PLUG_SWITCH, {})
    plug_power_raw = states.get(ENTITY_PLUG_POWER, {})
    plug_energy_raw = states.get(ENTITY_PLUG_ENERGY, {})
    person_raw = states.get(ENTITY_PERSON, {})
    weather_raw = states.get(ENTITY_WEATHER, {})

    switch = _switch_state(plug_switch_raw.get("state"))
    power_w = _parse_float(plug_power_raw.get("state"))
    energy_kwh = _parse_float(plug_energy_raw.get("state"))

    ac_running = power_w is not None and power_w >= ac_power_threshold_w

    person_attrs = person_raw.get("attributes") or {}
    person = PersonStatus(
        state=str(person_raw.get("state", "unknown")),
        latitude=_parse_float(person_attrs.get("latitude")),
        longitude=_parse_float(person_attrs.get("longitude")),
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
        plug=PlugStatus(switch=switch, power_w=power_w, energy_kwh=energy_kwh),
        ac_estimated_running=ac_running,
        person=person,
        indoor=_build_indoor(states),
        weather_outdoor=weather,
        updated_at=_now_kst_iso(),
    )


async def fetch_and_build_status(ha: HAClient, settings: Settings) -> StatusResponse:
    states = await ha.get_states_for(STATUS_ENTITY_IDS)
    return build_status_from_states(
        states,
        ac_power_threshold_w=settings.ac_power_threshold_w,
    )
