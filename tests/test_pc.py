from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.constants import ENTITY_PC_SWITCH
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


def test_pc_requires_api_key():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/v1/pc", json={"action": "on"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"


def test_pc_on_calls_switch_turn_on():
    app, _ = _app_with_key()
    with patch("app.routers.pc.HAClient") as mock_cls:
        mock_cls.return_value.call_service = AsyncMock(return_value=[])
        mock_cls.return_value.get_state = AsyncMock(
            return_value={"entity_id": ENTITY_PC_SWITCH, "state": "on"}
        )
        client = TestClient(app)
        resp = client.post(
            "/api/v1/pc",
            json={"action": "on"},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "switch": "on"}
    mock_cls.return_value.call_service.assert_awaited_once_with(
        "switch",
        "turn_on",
        {"entity_id": ENTITY_PC_SWITCH},
    )


def test_pc_off_calls_switch_turn_off():
    app, _ = _app_with_key()
    with patch("app.routers.pc.HAClient") as mock_cls:
        mock_cls.return_value.call_service = AsyncMock(return_value=[])
        mock_cls.return_value.get_state = AsyncMock(
            return_value={"entity_id": ENTITY_PC_SWITCH, "state": "off"}
        )
        client = TestClient(app)
        resp = client.post(
            "/api/v1/pc",
            json={"action": "off"},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "switch": "off"}
    mock_cls.return_value.call_service.assert_awaited_once_with(
        "switch",
        "turn_off",
        {"entity_id": ENTITY_PC_SWITCH},
    )


def test_pc_wake_requires_api_key():
    settings = Settings(
        ha_base_url="http://127.0.0.1:8123",
        ha_token="test-token",
        iot_api_key="test-key",
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    with patch("app.routers.pc.HAClient") as mock_cls:
        missing = client.post("/api/v1/pc/wake")
        wrong = client.post("/api/v1/pc/wake", headers={"X-API-Key": "wrong"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    mock_cls.assert_not_called()


def test_pc_wake_calls_ha_with_magic_packet_payload():
    settings = Settings(
        ha_base_url="http://127.0.0.1:8123",
        ha_token="test-token",
        iot_api_key="test-key",
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with patch("app.routers.pc.HAClient") as mock_cls:
        mock_cls.return_value.call_service = AsyncMock(return_value=[])
        response = TestClient(app).post(
            "/api/v1/pc/wake", headers={"X-API-Key": "test-key"}
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_cls.return_value.call_service.assert_awaited_once_with(
        "wake_on_lan",
        "send_magic_packet",
        {"mac": "00:D8:61:DD:54:3A", "broadcast_address": "192.168.0.255"},
    )
    mock_cls.return_value.get_state.assert_not_called()
