from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.constants import AC_COMMAND_OFF, AC_COMMAND_ON, AC_REMOTE_DEVICE, ENTITY_AC_REMOTE
from app.deps import verify_api_key
from app.main import create_app


def _app_with_key() -> tuple:
    settings = Settings(
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
    resp = client.post("/api/v1/ac", json={"action": "on"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"


def test_ac_on_calls_remote_send_command():
    app, _ = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_cls.return_value.call_service = AsyncMock(return_value=[])
        client = TestClient(app)
        resp = client.post(
            "/api/v1/ac",
            json={"action": "on"},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_cls.return_value.call_service.assert_awaited_once_with(
        "remote",
        "send_command",
        {
            "entity_id": ENTITY_AC_REMOTE,
            "device": AC_REMOTE_DEVICE,
            "command": AC_COMMAND_ON,
        },
    )


def test_ac_off_calls_remote_send_command():
    app, _ = _app_with_key()
    with patch("app.routers.ac.HAClient") as mock_cls:
        mock_cls.return_value.call_service = AsyncMock(return_value=[])
        client = TestClient(app)
        resp = client.post(
            "/api/v1/ac",
            json={"action": "off"},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    mock_cls.return_value.call_service.assert_awaited_once_with(
        "remote",
        "send_command",
        {
            "entity_id": ENTITY_AC_REMOTE,
            "device": AC_REMOTE_DEVICE,
            "command": AC_COMMAND_OFF,
        },
    )
