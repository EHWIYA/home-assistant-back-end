from unittest.mock import ANY, AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.constants import (
    AC_COMMAND_COOL_PRESET_17,
    AC_REMOTE_DEVICE,
    ENTITY_AC_AWAY_ENABLED,
    ENTITY_AC_LAST_ON,
    ENTITY_AC_MODE,
    ENTITY_AC_REMOTE,
    ENTITY_AC_AUTO_ENABLED,
    ENTITY_PLUG_SWITCH,
)
from app.deps import verify_api_key
from app.main import create_app


def _app_with_key() -> tuple:
    settings = Settings.model_construct(
        ha_base_url="http://127.0.0.1:8123",
        ha_token="test-token",
        iot_api_key="test-key",
    )
    app = create_app()
    get_settings.cache_clear()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[verify_api_key] = lambda: None
    return app, settings


def test_ac_requires_api_key():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/v1/ac", json={"mode": "cool"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"


def test_ac_returns_verified_state_and_request_id():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(return_value=[])
        mock_ha.get_state = AsyncMock(return_value={"state": "cool"})
        with patch("app.routers.ac.fetch_status", new=AsyncMock()) as mock_fetch_status:
            mock_fetch_status.return_value = type(
                "S",
                (),
                {
                    "plug": type("P", (), {"power_w": 742.0})(),
                    "ac_auto_state": None,
                    "ac_auto_enabled": False,
                    "ac_away_enabled": False,
                },
            )()
            client = TestClient(app)
            resp = client.post(
                "/api/v1/ac",
                json={"mode": "cool"},
                headers={"X-API-Key": settings.iot_api_key, "X-Request-ID": "req-123"},
            )

    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == "req-123"
    assert resp.json() == {
        "ok": True,
        "request_id": "req-123",
        "applied_mode": "cool",
        "power": "on",
        "auto_enabled": None,
        "away_enabled": None,
        "operating_mode": None,
    }
    assert mock_ha.call_service.await_count == 3
    first = mock_ha.call_service.await_args_list[0]
    second = mock_ha.call_service.await_args_list[1]
    third = mock_ha.call_service.await_args_list[2]
    assert first.args == (
        "remote",
        "send_command",
        {
            "entity_id": ENTITY_AC_REMOTE,
            "device": AC_REMOTE_DEVICE,
            "command": AC_COMMAND_COOL_PRESET_17,
        },
    )
    assert second.args == (
        "input_select",
        "select_option",
        {"entity_id": ENTITY_AC_MODE, "option": "cool"},
    )
    assert third.args == (
        "input_datetime",
        "set_datetime",
        {"entity_id": ENTITY_AC_LAST_ON, "datetime": ANY},
    )


def test_ac_returns_502_when_mode_sync_fails():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(side_effect=[[], Exception("boom")])
        client = TestClient(app)
        resp = client.post(
            "/api/v1/ac",
            json={"mode": "cool"},
            headers={"X-API-Key": settings.iot_api_key, "X-Request-ID": "req-sync-fail"},
        )

    assert resp.status_code == 502
    assert resp.headers["X-Request-ID"] == "req-sync-fail"
    payload = resp.json()
    assert payload["detail"]["code"] == "ac_mode_sync_failed"


def test_ac_returns_502_when_verified_mode_mismatch():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(return_value=[])
        mock_ha.get_state = AsyncMock(return_value={"state": "off"})
        with patch("app.routers.ac.fetch_status", new=AsyncMock()) as mock_fetch_status:
            mock_fetch_status.return_value = type("S", (), {"ac_estimated_running": False})()
            client = TestClient(app)
            resp = client.post(
                "/api/v1/ac",
                json={"mode": "cool"},
                headers={"X-API-Key": settings.iot_api_key},
            )

    assert resp.status_code == 502
    assert "X-Request-ID" in resp.headers
    payload = resp.json()
    assert payload["detail"]["code"] == "ac_state_mismatch"


def test_ac_state_includes_consistency_metadata():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.get_state = AsyncMock(return_value={"state": "cool"})
        with patch("app.routers.ac.fetch_status", new=AsyncMock()) as mock_fetch_status:
            mock_fetch_status.return_value = type(
                "S",
                (),
                {
                    "plug": type("P", (), {"power_w": 10.0})(),
                    "ac_estimated_running": False,
                    "ac_auto_enabled": True,
                    "ac_away_enabled": False,
                    "ac_mode": "cool",
                    "ac_last_run_mode": "cool",
                    "ac_auto_state": type("A", (), {"state": "on"})(),
                    "indoor": None,
                },
            )()
            with patch("app.routers.ac._read_last_control", return_value=None):
                client = TestClient(app)
                resp = client.get(
                    "/api/v1/ac/state",
                    headers={"X-API-Key": settings.iot_api_key},
                )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["mode"] == "cool"
    assert payload["power"] == "on"
    assert payload["away_enabled"] is False
    assert payload["last_run_mode"] == "cool"
    assert payload["running_source"] == "logical"
    assert payload["state_consistent"] is True
    assert payload["state_source"] == "composed(plug_w,ac_auto_state,ha_input_select)"
    assert payload["last_control_at"] is None
    assert payload["last_control_result"] is None


def test_ac_post_operating_mode_auto_mutex():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(return_value=[])
        async def _get_state(entity_id: str) -> dict:
            if entity_id == ENTITY_AC_MODE:
                return {"state": "auto"}
            return {"state": "on"}

        mock_ha.get_state = AsyncMock(side_effect=_get_state)
        with patch("app.routers.ac.fetch_status", new=AsyncMock()) as mock_fetch_status:
            mock_fetch_status.return_value = type(
                "S",
                (),
                {
                    "plug": type("P", (), {"power_w": 10.0})(),
                    "ac_auto_state": type("A", (), {"state": "off"})(),
                    "ac_auto_enabled": True,
                    "ac_away_enabled": False,
                },
            )()
            client = TestClient(app)
            resp = client.post(
                "/api/v1/ac",
                json={"mode": "auto", "operating_mode": "auto"},
                headers={"X-API-Key": settings.iot_api_key},
            )

    assert resp.status_code == 200
    assert resp.json()["operating_mode"] == "auto"
    away_calls = [
        c
        for c in mock_ha.call_service.await_args_list
        if c.args[:2] == ("input_boolean", "turn_off")
        and c.args[2].get("entity_id") == ENTITY_AC_AWAY_ENABLED
    ]
    auto_on_calls = [
        c
        for c in mock_ha.call_service.await_args_list
        if c.args[:2] == ("input_boolean", "turn_on")
        and c.args[2].get("entity_id") == ENTITY_AC_AUTO_ENABLED
    ]
    assert away_calls
    assert auto_on_calls


def test_ac_post_mutex_disables_auto_when_away_enabled():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(return_value=[])
        mock_ha.get_state = AsyncMock(return_value={"state": "cool"})
        with patch("app.routers.ac.fetch_status", new=AsyncMock()) as mock_fetch_status:
            mock_fetch_status.return_value = type(
                "S",
                (),
                {
                    "plug": type("P", (), {"power_w": 742.0})(),
                    "ac_auto_state": None,
                    "ac_auto_enabled": False,
                    "ac_away_enabled": True,
                    "ac_operating_mode": "away",
                },
            )()
            client = TestClient(app)
            resp = client.post(
                "/api/v1/ac",
                json={"mode": "cool", "auto_enabled": True, "away_enabled": True},
                headers={"X-API-Key": settings.iot_api_key},
            )

    assert resp.status_code == 200
    auto_off = [
        c
        for c in mock_ha.call_service.await_args_list
        if c.args[:2] == ("input_boolean", "turn_off")
        and c.args[2].get("entity_id") == ENTITY_AC_AUTO_ENABLED
    ]
    assert auto_off


def test_ac_thresholds_endpoint():
    app, settings = _app_with_key()
    client = TestClient(app)
    resp = client.get(
        "/api/v1/ac/thresholds",
        headers={"X-API-Key": settings.iot_api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "v2"
    assert "home_auto" in data
    assert "away" in data


def test_ac_auto_on_toggles_auto_and_plug():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(return_value=[])
        mock_ha.get_state = AsyncMock(return_value={"state": "on"})
        client = TestClient(app)
        resp = client.post(
            "/api/v1/ac/auto",
            json={"enabled": True},
            headers={"X-API-Key": settings.iot_api_key, "X-Request-ID": "req-auto-on"},
        )

    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == "req-auto-on"
    assert resp.json() == {
        "ok": True,
        "request_id": "req-auto-on",
        "auto_enabled": True,
        "plug_switch": "on",
    }
    away_off = mock_ha.call_service.await_args_list[0]
    auto_on = mock_ha.call_service.await_args_list[1]
    plug_on = mock_ha.call_service.await_args_list[2]
    assert away_off.args == (
        "input_boolean",
        "turn_off",
        {"entity_id": ENTITY_AC_AWAY_ENABLED},
    )
    assert auto_on.args == (
        "input_boolean",
        "turn_on",
        {"entity_id": ENTITY_AC_AUTO_ENABLED},
    )
    assert plug_on.args == (
        "switch",
        "turn_on",
        {"entity_id": ENTITY_PLUG_SWITCH},
    )


def test_ac_auto_off_only_toggles_boolean():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(return_value=[])
        mock_ha.get_state = AsyncMock(return_value={"state": "on"})
        client = TestClient(app)
        resp = client.post(
            "/api/v1/ac/auto",
            json={"enabled": False},
            headers={"X-API-Key": settings.iot_api_key},
        )

    assert resp.status_code == 200
    assert resp.json()["auto_enabled"] is False
    assert resp.json()["plug_switch"] == "on"
    assert mock_ha.call_service.await_count == 1
    assert mock_ha.call_service.await_args_list[0].args == (
        "input_boolean",
        "turn_off",
        {"entity_id": ENTITY_AC_AUTO_ENABLED},
    )


def test_ac_auto_returns_502_when_plug_sync_fails():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(side_effect=[[], [], Exception("plug boom")])
        client = TestClient(app)
        resp = client.post(
            "/api/v1/ac/auto",
            json={"enabled": True},
            headers={"X-API-Key": settings.iot_api_key, "X-Request-ID": "req-auto-fail"},
        )

    assert resp.status_code == 502
    assert resp.headers["X-Request-ID"] == "req-auto-fail"
    payload = resp.json()
    assert payload["detail"]["code"] == "ac_auto_plug_sync_failed"


def test_ac_auto_returns_502_when_plug_state_mismatch():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(return_value=[])
        mock_ha.get_state = AsyncMock(return_value={"state": "off"})
        client = TestClient(app)
        resp = client.post(
            "/api/v1/ac/auto",
            json={"enabled": True},
            headers={"X-API-Key": settings.iot_api_key},
        )

    assert resp.status_code == 502
    payload = resp.json()
    assert payload["detail"]["code"] == "ac_auto_plug_state_mismatch"


def test_ac_mode_auto_skips_ir_and_sets_input_select():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(return_value=[])
        mock_ha.get_state = AsyncMock(return_value={"state": "auto"})
        with patch("app.routers.ac.fetch_status", new=AsyncMock()) as mock_fetch_status:
            mock_fetch_status.return_value = type(
                "S",
                (),
                {
                    "plug": type("P", (), {"power_w": 10.0})(),
                    "ac_auto_state": type("A", (), {"state": "off"})(),
                    "ac_auto_enabled": True,
                    "ac_away_enabled": False,
                },
            )()
            client = TestClient(app)
            resp = client.post(
                "/api/v1/ac",
                json={"mode": "auto"},
                headers={"X-API-Key": settings.iot_api_key},
            )

    assert resp.status_code == 200
    assert resp.json()["applied_mode"] == "auto"
    assert mock_ha.call_service.await_count == 1
    assert mock_ha.call_service.await_args_list[0].args == (
        "input_select",
        "select_option",
        {"entity_id": ENTITY_AC_MODE, "option": "auto"},
    )


def test_ac_away_enabled_toggle():
    app, settings = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_ha = mock_cls.return_value
        mock_ha.call_service = AsyncMock(return_value=[])
        mock_ha.get_state = AsyncMock(return_value={"state": "cool"})
        with patch("app.routers.ac.fetch_status", new=AsyncMock()) as mock_fetch_status:
            mock_fetch_status.return_value = type(
                "S",
                (),
                {
                    "plug": type("P", (), {"power_w": 742.0})(),
                    "ac_auto_state": None,
                    "ac_auto_enabled": False,
                    "ac_away_enabled": True,
                },
            )()
            client = TestClient(app)
            resp = client.post(
                "/api/v1/ac",
                json={"mode": "cool", "away_enabled": True},
                headers={"X-API-Key": settings.iot_api_key},
            )

    assert resp.status_code == 200
    assert resp.json()["away_enabled"] is True
    away_call = mock_ha.call_service.await_args_list[3]
    assert away_call.args == (
        "input_boolean",
        "turn_on",
        {"entity_id": ENTITY_AC_AWAY_ENABLED},
    )
