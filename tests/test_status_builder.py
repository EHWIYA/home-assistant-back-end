import json
from pathlib import Path

from app.services.status_builder import build_status_from_states

FIXTURE = Path(__file__).parent / "fixtures" / "ha_states.json"


def test_build_status_from_fixture():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    status = build_status_from_states(
        states, ac_power_threshold_w=50, pc_power_threshold_w=50
    )

    assert status.plug.switch == "on"
    assert status.plug.power_w == 742.0
    assert status.plug.energy_kwh == 12.34
    assert status.pc.switch == "on"
    assert status.pc.power_w == 85.5
    assert status.pc.energy_today_kwh == 0.42
    assert status.pc.energy_month_kwh == 3.15
    assert status.pc.online is True
    assert status.pc.wifi_signal_level == 3
    assert status.pc.overload is False
    assert status.pc.estimated_running is True
    assert status.ac_estimated_running is True
    assert status.person.state == "not_home"
    assert status.person.latitude == 37.473
    assert status.weather_outdoor is not None
    assert status.weather_outdoor.temperature == 18.2
    assert status.indoor is None
    assert status.updated_at.endswith("+09:00") or "+09:" in status.updated_at


def test_ac_off_below_threshold():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["sensor.hwiya_home_power"]["state"] = "10"
    status = build_status_from_states(
        states, ac_power_threshold_w=50, pc_power_threshold_w=50
    )
    assert status.ac_estimated_running is False


def test_pc_estimated_running_below_threshold():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["sensor.hwiya_pc_current_consumption"]["state"] = "10"
    status = build_status_from_states(
        states, ac_power_threshold_w=50, pc_power_threshold_w=50
    )
    assert status.pc.estimated_running is False


def test_pc_defaults_when_entities_missing():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for key in list(states):
        if key.startswith(("switch.hwiya_pc", "sensor.hwiya_pc", "binary_sensor.hwiya_pc")):
            del states[key]
    status = build_status_from_states(
        states, ac_power_threshold_w=50, pc_power_threshold_w=50
    )
    assert status.pc.switch == "unknown"
    assert status.pc.power_w is None
    assert status.pc.online is False
    assert status.pc.overload is False
    assert status.pc.estimated_running is False


def test_unavailable_power_is_null():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    states["sensor.hwiya_home_power"]["state"] = "unavailable"
    status = build_status_from_states(states, ac_power_threshold_w=50, pc_power_threshold_w=50)
    assert status.plug.power_w is None
    assert status.ac_estimated_running is False


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
    status = build_status_from_states(_states_with_indoor(), ac_power_threshold_w=50, pc_power_threshold_w=50)
    assert status.indoor is not None
    assert status.indoor.temperature == 27.2
    assert status.indoor.humidity == 49.0


def test_indoor_celsius_passthrough():
    states = _states_with_indoor(temp_state="27.5", temp_unit="°C")
    status = build_status_from_states(states, ac_power_threshold_w=50, pc_power_threshold_w=50)
    assert status.indoor is not None
    assert status.indoor.temperature == 27.5
    assert status.indoor.humidity == 49.0


def test_indoor_null_when_sensor_missing():
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    status = build_status_from_states(states, ac_power_threshold_w=50, pc_power_threshold_w=50)
    assert status.indoor is None


def test_indoor_null_when_unavailable():
    states = _states_with_indoor(temp_state="unavailable")
    status = build_status_from_states(states, ac_power_threshold_w=50, pc_power_threshold_w=50)
    assert status.indoor is None


def test_indoor_null_when_humidity_unknown():
    states = _states_with_indoor(humidity_state="unknown")
    status = build_status_from_states(states, ac_power_threshold_w=50, pc_power_threshold_w=50)
    assert status.indoor is None
