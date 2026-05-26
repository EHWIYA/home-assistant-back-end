import json
from pathlib import Path

from app.config import Settings
from app.services.ha_ws_cache import HAStateCache, ha_websocket_url
from app.services.status_builder import build_status_from_states

FIXTURE = Path(__file__).parent / "fixtures" / "ha_states.json"


def test_ha_websocket_url_from_http():
    assert ha_websocket_url("http://127.0.0.1:8123") == "ws://127.0.0.1:8123/api/websocket"


def test_ha_websocket_url_from_https():
    assert (
        ha_websocket_url("https://ha.example.com:8123/")
        == "wss://ha.example.com:8123/api/websocket"
    )


def test_apply_state_dict_filters_entities():
    HAStateCache.reset_for_tests()
    cache = HAStateCache()

    assert cache.apply_state_dict("switch.hwiya_home", {"entity_id": "switch.hwiya_home", "state": "on"})
    assert not cache.apply_state_dict("light.other", {"entity_id": "light.other", "state": "on"})
    assert cache.get_states_copy()["switch.hwiya_home"]["state"] == "on"


def test_apply_get_states_result_filters():
    HAStateCache.reset_for_tests()
    cache = HAStateCache()
    states = [
        {"entity_id": "switch.hwiya_home", "state": "on"},
        {"entity_id": "light.unrelated", "state": "off"},
    ]
    cache.apply_get_states_result(states)
    copied = cache.get_states_copy()
    assert "switch.hwiya_home" in copied
    assert "light.unrelated" not in copied


def test_build_status_from_cache_matches_builder():
    HAStateCache.reset_for_tests()
    cache = HAStateCache()
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cache.apply_get_states_result(list(states.values()))
    cache._snapshot_ready = True
    cache._connected = True

    settings = Settings.model_construct(
        ha_base_url="http://127.0.0.1:8123",
        ha_token="t",
        iot_api_key="k",
        ac_power_threshold_w=50.0,
        pc_power_threshold_w=50.0,
    )
    from_cache = cache.build_status(settings)
    direct = build_status_from_states(states, ac_power_threshold_w=50, pc_power_threshold_w=50)
    assert from_cache.plug == direct.plug
    assert from_cache.pc == direct.pc
    assert from_cache.ac_estimated_running == direct.ac_estimated_running
