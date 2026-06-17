from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import verify_api_key
from app.exceptions import MoodError
from app.main import create_app
from app.services.mood_client import MoodClient, build_command, clear_integration_cache


def _app_with_key(**settings_overrides) -> tuple:
    defaults = {
        "ha_base_url": "http://127.0.0.1:8123",
        "ha_token": "test-token",
        "iot_api_key": "test-key",
        "mood_gh_room": "자취방",
        "mood_gh_device": "무드등",
        "mood_light_entity_id": "",
    }
    settings = Settings(**{**defaults, **settings_overrides})
    app = create_app()
    get_settings.cache_clear()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[verify_api_key] = lambda: None
    return app, settings


@pytest.fixture(autouse=True)
def _clear_mood_integration_cache():
    clear_integration_cache()
    yield
    clear_integration_cache()


def test_mood_requires_api_key():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/v1/mood/power", json={"on": True})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"


def test_mood_capabilities_google_home_only():
    app, _ = _app_with_key()
    client = TestClient(app)
    resp = client.get("/api/v1/mood/capabilities", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert "power" in data["actions"]
    assert "color-rgb" not in data["actions"]
    assert data["color_modes"] == ["named"]
    assert data["supports_rgb"] is False
    assert data["supports_hex"] is False
    assert data["supports_state"] is False


def test_mood_capabilities_ha_direct():
    app, _ = _app_with_key(mood_light_entity_id="light.jacwibang_mood")
    client = TestClient(app)
    resp = client.get("/api/v1/mood/capabilities", headers={"X-API-Key": "test-key"})
    data = resp.json()
    assert "color-rgb" in data["actions"]
    assert data["color_modes"] == ["named", "rgb"]
    assert data["supports_rgb"] is True
    assert data["supports_state"] is True


def test_mood_meta_google_home_only():
    app, _ = _app_with_key()
    client = TestClient(app)
    resp = client.get("/api/v1/mood/meta", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    assert resp.json() == {
        "room": "자취방",
        "device": "무드등",
        "path": "google_assistant_sdk",
        "control_paths": ["google_assistant_sdk"],
        "entity_id": None,
        "state_readable": False,
    }


def test_mood_meta_ha_direct():
    app, _ = _app_with_key(mood_light_entity_id="light.jacwibang_mood")
    client = TestClient(app)
    resp = client.get("/api/v1/mood/meta", headers={"X-API-Key": "test-key"})
    data = resp.json()
    assert data["path"] == "home_assistant"
    assert data["entity_id"] == "light.jacwibang_mood"
    assert data["state_readable"] is True


def test_mood_state_google_home_only():
    app, _ = _app_with_key()
    client = TestClient(app)
    resp = client.get("/api/v1/mood/state", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["on"] is None
    assert data["state_readable"] is False
    assert "상태 읽기 미지원" in data["note"]


def test_mood_state_ha_direct():
    app, _ = _app_with_key(mood_light_entity_id="light.jacwibang_mood")
    with patch("app.services.mood_service.HAClient") as mock_cls:
        mock_cls.return_value.get_state = AsyncMock(
            return_value={
                "state": "on",
                "attributes": {"brightness": 128, "rgb_color": [255, 87, 51]},
            }
        )
        client = TestClient(app)
        resp = client.get("/api/v1/mood/state", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["on"] is True
    assert data["brightness"] == 50
    assert data["color"] == "#ff5733"
    assert data["rgb"] == [255, 87, 51]
    assert data["state_readable"] is True


def test_build_command_phrases():
    assert build_command(room="자취방", device="무드등", action="on") == "자취방 무드등 켜줘"
    assert build_command(room="자취방", device="무드등", action="off") == "자취방 무드등 꺼줘"
    assert (
        build_command(room="자취방", device="무드등", action="brightness", percent=30)
        == "자취방 무드등 밝기 30%로 해줘"
    )
    assert (
        build_command(room="자취방", device="무드등", action="color", color="red")
        == "자취방 무드등 빨간색으로 해줘"
    )
    assert (
        build_command(room="자취방", device="무드등", action="color", color="rainbow")
        == "자취방 무드등 무지개 모드 켜줘"
    )


def test_mood_power_on():
    app, _ = _app_with_key()
    with patch("app.services.mood_service.MoodClient") as mock_cls:
        mock_cls.return_value.send_power = AsyncMock(return_value="자취방 무드등 켜줘")
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/power",
            json={"on": True},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "command": "자취방 무드등 켜줘",
        "control_path": "google_assistant_sdk",
    }


def test_mood_power_on_ha_direct():
    app, _ = _app_with_key(mood_light_entity_id="light.jacwibang_mood")
    with patch("app.services.mood_service.HAClient") as mock_cls:
        mock_cls.return_value.call_service = AsyncMock(return_value=[])
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/power",
            json={"on": True},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    assert resp.json()["control_path"] == "home_assistant"
    mock_cls.return_value.call_service.assert_awaited_once_with(
        "light",
        "turn_on",
        {"entity_id": "light.jacwibang_mood"},
    )


def test_mood_brightness_ha_direct():
    app, _ = _app_with_key(mood_light_entity_id="light.jacwibang_mood")
    with patch("app.services.mood_service.HAClient") as mock_cls:
        mock_cls.return_value.call_service = AsyncMock(return_value=[])
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/brightness",
            json={"percent": 50},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    mock_cls.return_value.call_service.assert_awaited_once_with(
        "light",
        "turn_on",
        {"entity_id": "light.jacwibang_mood", "brightness_pct": 50},
    )


def test_mood_color_rgb_not_supported_without_entity():
    app, _ = _app_with_key()
    client = TestClient(app)
    resp = client.post(
        "/api/v1/mood/color-rgb",
        json={"hex": "#ff5733"},
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "mood_rgb_not_supported"


def test_mood_color_rgb_ha_direct():
    app, _ = _app_with_key(mood_light_entity_id="light.jacwibang_mood")
    with patch("app.services.mood_service.HAClient") as mock_cls:
        mock_cls.return_value.call_service = AsyncMock(return_value=[])
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/color-rgb",
            json={"hex": "#ff5733"},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    mock_cls.return_value.call_service.assert_awaited_once_with(
        "light",
        "turn_on",
        {"entity_id": "light.jacwibang_mood", "rgb_color": [255, 87, 51]},
    )


def test_mood_color():
    app, _ = _app_with_key()
    with patch("app.services.mood_service.MoodClient") as mock_cls:
        mock_cls.return_value.send_color = AsyncMock(return_value="자취방 무드등 파란색으로 해줘")
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/color",
            json={"name": "blue"},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    mock_cls.return_value.send_color.assert_awaited_once_with("blue")


def test_mood_color_temperature():
    app, _ = _app_with_key()
    with patch("app.services.mood_service.MoodClient") as mock_cls:
        mock_cls.return_value.send_color = AsyncMock(return_value="자취방 무드등 따뜻한 색으로 해줘")
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/color-temperature",
            json={"mode": "warm"},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    mock_cls.return_value.send_color.assert_awaited_once_with("warm")


def test_mood_command_escape_hatch():
    app, _ = _app_with_key()
    with patch("app.services.mood_service.MoodClient") as mock_cls:
        mock_cls.return_value.send_raw_command = AsyncMock(return_value="자취방 무드등 깜빡여줘")
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/command",
            json={"command": "자취방 무드등 깜빡여줘"},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    mock_cls.return_value.send_raw_command.assert_awaited_once_with("자취방 무드등 깜빡여줘")


def test_mood_brightness_validation():
    app, _ = _app_with_key()
    client = TestClient(app)
    resp = client.post(
        "/api/v1/mood/brightness",
        json={"percent": 0},
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 422


def test_mood_integration_missing_returns_503():
    app, _ = _app_with_key()
    with patch("app.services.mood_service.MoodClient") as mock_cls:
        mock_cls.return_value.send_power = AsyncMock(
            side_effect=MoodError(
                "google_assistant_sdk integration not loaded",
                status_code=503,
                code="mood_integration_missing",
            )
        )
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/power",
            json={"on": True},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "mood_integration_missing"


@pytest.mark.asyncio
async def test_check_integration_uses_cache_within_ttl():
    settings = Settings(
        ha_base_url="http://127.0.0.1:8123",
        ha_token="test-token",
        mood_integration_cache_ttl_seconds=120,
    )
    client = MoodClient(settings)
    with patch.object(client, "_fetch_integration", AsyncMock(return_value=True)) as mock_fetch:
        assert await client.check_integration() is True
        assert await client.check_integration() is True
        mock_fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_integration_refetches_when_cache_disabled():
    settings = Settings(
        ha_base_url="http://127.0.0.1:8123",
        ha_token="test-token",
        mood_integration_cache_ttl_seconds=-1,
    )
    client = MoodClient(settings)
    with patch.object(client, "_fetch_integration", AsyncMock(return_value=True)) as mock_fetch:
        assert await client.check_integration() is True
        assert await client.check_integration() is True
        assert mock_fetch.await_count == 2
