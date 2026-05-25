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
