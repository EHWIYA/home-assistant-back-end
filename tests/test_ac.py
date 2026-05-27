from unittest.mock import ANY, AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.constants import (
    AC_COMMAND_COOL_PRESET_17,
    AC_REMOTE_DEVICE,
    ENTITY_AC_LAST_ON,
    ENTITY_AC_MODE,
    ENTITY_AC_REMOTE,
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
            mock_fetch_status.return_value = type("S", (), {"ac_estimated_running": True})()
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
    payload = resp.json()
    assert payload["detail"]["code"] == "ac_state_mismatch"
