"""공통 테스트 픽스처 — HA WebSocket 캐시 lifespan이 실제 HA에 붙지 않게."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.ha_ws_cache import HAStateCache, get_ha_state_cache


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
