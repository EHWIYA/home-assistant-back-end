import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import verify_api_key, verify_api_key_header_or_query
from app.main import create_app
from app.models.schemas import StatusResponse
from app.services.ha_ws_cache import HAStateCache, get_ha_state_cache
from app.services.status_builder import build_status_from_states

FIXTURE = Path(__file__).parent / "fixtures" / "ha_states.json"


def _settings() -> Settings:
    return Settings.model_construct(
        ha_base_url="http://127.0.0.1:8123",
        ha_token="test-token",
        iot_api_key="test-key",
        ac_power_threshold_w=50.0,
        pc_power_threshold_w=50.0,
        estimate_rate_won_per_kwh=199.28,
    )


def _status_from_fixture() -> StatusResponse:
    states = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return build_status_from_states(
        states,
        ac_power_threshold_w=50,
        pc_power_threshold_w=50,
        estimate_rate_won_per_kwh=199.28,
    )


def _app_with_key() -> TestClient:
    settings = _settings()
    app = create_app()
    get_settings.cache_clear()
    HAStateCache.reset_for_tests()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[verify_api_key] = lambda: None
    app.dependency_overrides[verify_api_key_header_or_query] = lambda: None
    with patch.object(get_ha_state_cache(), "start"):
        with patch.object(get_ha_state_cache(), "stop", new_callable=AsyncMock):
            return TestClient(app)


def test_status_uses_cache_when_connected():
    client = _app_with_key()
    expected = _status_from_fixture()
    cache = get_ha_state_cache()
    cache._connected = True
    cache._snapshot_ready = True
    cache.apply_get_states_result(list(json.loads(FIXTURE.read_text(encoding="utf-8")).values()))

    with patch("app.services.status_service.HAClient") as mock_ha:
        resp = client.get("/api/v1/status", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    mock_ha.assert_not_called()
    data = resp.json()
    assert data["plug"]["switch"] == expected.plug.switch
    assert data["pc"]["estimated_running"] == expected.pc.estimated_running


def test_status_rest_fallback_when_ws_down():
    client = _app_with_key()
    expected = _status_from_fixture()
    cache = get_ha_state_cache()
    cache._connected = False
    cache._snapshot_ready = False

    with patch("app.services.status_service.fetch_and_build_status", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = expected
        resp = client.get("/api/v1/status", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    mock_fetch.assert_awaited_once()


def test_status_stream_requires_api_key():
    HAStateCache.reset_for_tests()
    get_settings.cache_clear()
    app = create_app()
    with patch.object(get_ha_state_cache(), "start"):
        with patch.object(get_ha_state_cache(), "stop", new_callable=AsyncMock):
            client = TestClient(app)
    resp = client.get("/api/v1/status/stream")
    assert resp.status_code == 401


def test_status_stream_snapshot_event():
    client = _app_with_key()
    expected = _status_from_fixture()

    def _fake_subscribe() -> asyncio.Queue[str | None]:
        return asyncio.Queue()

    with patch("app.routers.status.fetch_status", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = expected
        with patch.object(get_ha_state_cache(), "subscribe", side_effect=_fake_subscribe):
            with client.stream(
                "GET",
                "/api/v1/status/stream",
                headers={"X-API-Key": "test-key"},
            ) as resp:
                assert resp.status_code == 200
                chunk = next(resp.iter_text())
                resp.close()
    assert chunk.startswith("event: snapshot\n")
    assert "switch" in chunk
