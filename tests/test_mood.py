from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import verify_api_key
from app.exceptions import MoodError
from app.main import create_app
from app.services.mood_client import build_command


def _app_with_key() -> tuple:
    settings = Settings(
        ha_base_url="http://127.0.0.1:8123",
        ha_token="test-token",
        iot_api_key="test-key",
        mood_gh_room="자취방",
        mood_gh_device="무드등",
    )
    app = create_app()
    get_settings.cache_clear()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[verify_api_key] = lambda: None
    return app, settings


def test_mood_requires_api_key():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/v1/mood/power", json={"on": True})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"


def test_mood_capabilities():
    app, _ = _app_with_key()
    client = TestClient(app)
    resp = client.get("/api/v1/mood/capabilities", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert "power" in data["actions"]
    assert "red" in data["colors"]
    assert "rainbow" in data["colors"]
    assert data["brightness_range"] == [1, 100]


def test_mood_meta():
    app, _ = _app_with_key()
    client = TestClient(app)
    resp = client.get("/api/v1/mood/meta", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    assert resp.json() == {
        "room": "자취방",
        "device": "무드등",
        "path": "google_assistant_sdk",
        "state_readable": False,
    }


def test_mood_state_always_null():
    app, _ = _app_with_key()
    client = TestClient(app)
    resp = client.get("/api/v1/mood/state", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["on"] is None
    assert data["brightness"] is None
    assert data["color"] is None
    assert "상태 읽기 미지원" in data["note"]


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
    with patch("app.routers.mood.MoodClient") as mock_cls:
        mock_cls.return_value.send_power = AsyncMock(return_value="자취방 무드등 켜줘")
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/power",
            json={"on": True},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "command": "자취방 무드등 켜줘"}
    mock_cls.return_value.send_power.assert_awaited_once_with(True)


def test_mood_power_off():
    app, _ = _app_with_key()
    with patch("app.routers.mood.MoodClient") as mock_cls:
        mock_cls.return_value.send_power = AsyncMock(return_value="자취방 무드등 꺼줘")
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/power",
            json={"on": False},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    assert resp.json()["command"] == "자취방 무드등 꺼줘"


def test_mood_brightness():
    app, _ = _app_with_key()
    with patch("app.routers.mood.MoodClient") as mock_cls:
        mock_cls.return_value.send_brightness = AsyncMock(
            return_value="자취방 무드등 밝기 50%로 해줘"
        )
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mood/brightness",
            json={"percent": 50},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    mock_cls.return_value.send_brightness.assert_awaited_once_with(50)


def test_mood_color():
    app, _ = _app_with_key()
    with patch("app.routers.mood.MoodClient") as mock_cls:
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
    with patch("app.routers.mood.MoodClient") as mock_cls:
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
    with patch("app.routers.mood.MoodClient") as mock_cls:
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
    with patch("app.routers.mood.MoodClient") as mock_cls:
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
