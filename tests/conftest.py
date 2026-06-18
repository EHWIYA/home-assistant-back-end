"""공통 테스트 픽스처 — CI·로컬 모두 동일 키, HA WS·SSE hang 방지."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.config import get_settings
from app.services.ha_ws_cache import HAStateCache, get_ha_state_cache

# CI에는 .env 없음 — get_settings().iot_api_key 직접 쓰지 말 것
TEST_IOT_API_KEY = "test-key"


def api_key_headers() -> dict[str, str]:
    return {"X-API-Key": TEST_IOT_API_KEY}


@pytest.fixture(autouse=True)
def _test_env_settings(monkeypatch: pytest.MonkeyPatch):
    """로컬 .env 유무와 무관하게 인증 테스트 일관."""
    monkeypatch.setenv("IOT_API_KEY", TEST_IOT_API_KEY)
    monkeypatch.setenv("HA_TOKEN", "test-ha-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _isolate_ha_ws_cache():
    """TestClient lifespan이 WS 재연결 루프(최대 90s/block)를 돌리지 않도록."""
    HAStateCache.reset_for_tests()
    cache = get_ha_state_cache()
    with (
        patch.object(cache, "start"),
        patch.object(cache, "stop", new_callable=AsyncMock),
    ):
        yield
    HAStateCache.reset_for_tests()
