import json
from pathlib import Path

from app.services.status_builder import (
    build_status_from_states,
    derive_ac_operating_mode,
    is_ac_automation_blocked,
    resolve_ac_mutex_toggles,
    resolve_ha_ac_mode,
)

FIXTURE = Path(__file__).parent / "fixtures" / "ha_states.json"
ESTIMATE_RATE = 199.28


def _build(states: dict, **overrides: float) -> object:
    return build_status_from_states(
        states,
        ac_power_threshold_w=overrides.get("ac_power_threshold_w", 50),
        pc_power_threshold_w=overrides.get("pc_power_threshold_w", 50),
        estimate_rate_won_per_kwh=overrides.get("estimate_rate_won_per_kwh", ESTIMATE_RATE),
    )


def test_build_status_from_fixture():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    status = _build(states)

    assert status.plug.switch == "on"
    assert status.plug.power_w == 742.0
    assert status.plug.energy_kwh == 12.34
    assert status.plug.estimated_cost_won == 2459
    assert status.pc.switch == "on"
    assert status.pc.power_w == 85.5
    assert status.pc.energy_today_kwh == 0.42
    assert status.pc.energy_month_kwh == 3.15
    assert status.pc.estimated_cost_today_won == 84
    assert status.pc.estimated_cost_month_won == 628
    assert status.electricity.rate_won_per_kwh == ESTIMATE_RATE
    assert status.pc.online is True
    assert status.pc.wifi_signal_level == 3
    assert status.pc.overload is False
    assert status.pc.estimated_running is True
    assert status.ac_estimated_running is True
    assert status.weather_outdoor is not None
    assert status.weather_outdoor.temperature == 18.2
    assert status.ac_auto_enabled is True
    assert status.ac_away_enabled is False
    assert status.ac_operating_mode == "auto"
    assert status.ac_mode == "cool"
    assert status.ac_last_run_mode == "cool"
    assert status.ac_auto_state is not None
    assert status.ac_auto_state.state == "on"
    assert status.ac_auto_state.last_on == "2026-05-26 10:10:00"
    assert status.ac_auto_state.last_off == "2026-05-26 09:30:00"
    assert status.ac_auto_state.last_transition == "2026-05-26 10:10:00"
    assert status.ac_auto_state.last_run_mode == "cool"
    assert status.indoor is None
    assert status.updated_at.endswith("+09:00") or "+09:" in status.updated_at


def test_ac_off_below_threshold():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["sensor.hwiya_home_power"]["state"] = "10"
    states["sensor.hwiya_ac_auto_state"]["state"] = "off"
    status = _build(states)
    assert status.ac_estimated_running is False


def test_ac_running_when_logical_on_below_plug_threshold():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["sensor.hwiya_home_power"]["state"] = "10"
    states["sensor.hwiya_ac_auto_state"]["state"] = "on"
    status = _build(states)
    assert status.ac_estimated_running is True


def test_pc_estimated_running_below_threshold():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["sensor.hwiya_pc_current_consumption"]["state"] = "10"
    status = _build(states)
    assert status.pc.estimated_running is False


def test_pc_defaults_when_entities_missing():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for key in list(states):
        if key.startswith(("switch.hwiya_pc", "sensor.hwiya_pc", "binary_sensor.hwiya_pc")):
            del states[key]
    status = _build(states)
    assert status.pc.switch == "unknown"
    assert status.pc.power_w is None
    assert status.pc.estimated_cost_today_won is None
    assert status.pc.estimated_cost_month_won is None
    assert status.pc.online is False
    assert status.pc.overload is False
    assert status.pc.estimated_running is False


def test_unavailable_power_is_null():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["sensor.hwiya_home_power"]["state"] = "unavailable"
    states["sensor.hwiya_ac_auto_state"]["state"] = "off"
    status = _build(states)
    assert status.plug.power_w is None
    assert status.ac_estimated_running is False


def test_estimate_cost_null_when_energy_unavailable():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["sensor.hwiya_home_energy"]["state"] = "unavailable"
    status = _build(states)
    assert status.plug.energy_kwh is None
    assert status.plug.estimated_cost_won is None


def test_estimate_cost_rounding():
    from app.services.status_builder import _estimate_cost_won

    assert _estimate_cost_won(0.897, ESTIMATE_RATE) == 179
    assert _estimate_cost_won(6.367, ESTIMATE_RATE) == 1269


def _states_with_indoor(
    temp_state: str = "81",
    humidity_state: str = "49",
    *,
    temp_unit: str = "°F",
) -> dict:
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["sensor.hwiya_sensor_temperature"] = {
        "entity_id": "sensor.hwiya_sensor_temperature",
        "state": temp_state,
        "attributes": {"unit_of_measurement": temp_unit},
    }
    states["sensor.hwiya_sensor_humidity"] = {
        "entity_id": "sensor.hwiya_sensor_humidity",
        "state": humidity_state,
        "attributes": {"unit_of_measurement": "%"},
    }
    return states


def test_indoor_fahrenheit_to_celsius():
    status = _build(_states_with_indoor())
    assert status.indoor is not None
    assert status.indoor.temperature == 27.2
    assert status.indoor.humidity == 49.0


def test_indoor_celsius_passthrough():
    states = _states_with_indoor(temp_state="27.5", temp_unit="°C")
    status = _build(states)
    assert status.indoor is not None
    assert status.indoor.temperature == 27.5
    assert status.indoor.humidity == 49.0


def test_indoor_null_when_sensor_missing():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    status = _build(states)
    assert status.indoor is None


def test_indoor_null_when_unavailable():
    states = _states_with_indoor(temp_state="unavailable")
    status = _build(states)
    assert status.indoor is None


def test_indoor_null_when_humidity_unknown():
    states = _states_with_indoor(humidity_state="unknown")
    status = _build(states)
    assert status.indoor is None


def test_ac_auto_state_placeholder_unknown_maps_to_null():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["sensor.hwiya_ac_auto_state"] = {
        "entity_id": "sensor.hwiya_ac_auto_state",
        "state": "unknown",
        "attributes": {
            "last_on": "unknown",
            "last_off": "unknown",
            "last_transition": "unknown",
        },
    }
    status = _build(states)
    assert status.ac_auto_state is not None
    assert status.ac_auto_state.state == "unknown"
    assert status.ac_auto_state.last_on is None
    assert status.ac_auto_state.last_off is None
    assert status.ac_auto_state.last_transition is None


def test_ac_last_run_mode_empty_string_maps_to_null():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["input_text.hwiya_ac_last_run_mode"] = {
        "entity_id": "input_text.hwiya_ac_last_run_mode",
        "state": "",
        "attributes": {},
    }
    states["sensor.hwiya_ac_auto_state"]["attributes"]["last_run_mode"] = "dry"
    status = _build(states)
    assert status.ac_last_run_mode is None


def test_ac_last_run_mode_prefers_input_text_over_sensor_attr():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["input_text.hwiya_ac_last_run_mode"]["state"] = "dry"
    states["sensor.hwiya_ac_auto_state"]["attributes"]["last_run_mode"] = "cool"
    status = _build(states)
    assert status.ac_last_run_mode == "dry"


def test_ac_mode_auto_from_input_select():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["input_select.hwiya_ac_mode"]["state"] = "auto"
    status = _build(states)
    assert status.ac_mode == "auto"


def test_ac_away_enabled_true():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["input_boolean.hwiya_ac_away_enabled"]["state"] = "on"
    status = _build(states)
    assert status.ac_away_enabled is True
    assert status.ac_operating_mode == "away"


def test_derive_ac_operating_mode_away_over_auto():
    assert derive_ac_operating_mode(auto_enabled=True, away_enabled=True) == "away"


def test_resolve_ac_mutex_both_true_prefers_away():
    assert resolve_ac_mutex_toggles(auto_enabled=True, away_enabled=True) == (False, True)


def test_resolve_ac_mutex_operating_mode_auto():
    assert resolve_ac_mutex_toggles(operating_mode="auto") == (True, False)


def test_resolve_ha_ac_mode_off_with_operating_mode_auto():
    assert resolve_ha_ac_mode(mode="off", operating_mode="auto") == "auto"


def test_resolve_ha_ac_mode_off_with_operating_mode_away():
    assert resolve_ha_ac_mode(mode="off", operating_mode="away") == "auto"


def test_resolve_ha_ac_mode_off_with_auto_toggle():
    assert resolve_ha_ac_mode(mode="off", auto_toggle=True) == "auto"


def test_resolve_ha_ac_mode_off_manual_stays_off():
    assert resolve_ha_ac_mode(mode="off", operating_mode="manual") == "off"


def test_resolve_ha_ac_mode_cool_unchanged():
    assert resolve_ha_ac_mode(mode="cool", operating_mode="auto") == "cool"


def test_is_ac_automation_blocked_when_auto_on_and_mode_off():
    assert is_ac_automation_blocked(mode="off", auto_enabled=True, away_enabled=False) is True


def test_is_ac_automation_blocked_when_away_on_and_mode_off():
    assert is_ac_automation_blocked(mode="off", auto_enabled=False, away_enabled=True) is True


def test_is_ac_automation_blocked_false_when_mode_auto():
    assert is_ac_automation_blocked(mode="auto", auto_enabled=True, away_enabled=False) is False


def test_is_ac_automation_blocked_false_when_manual_off():
    assert is_ac_automation_blocked(mode="off", auto_enabled=False, away_enabled=False) is False


def test_ac_operating_mode_manual():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["input_boolean.hwiya_ac_auto_enabled"]["state"] = "off"
    states["input_boolean.hwiya_ac_away_enabled"]["state"] = "off"
    status = _build(states)
    assert status.ac_operating_mode == "manual"
