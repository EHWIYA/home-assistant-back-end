import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.config import Settings
from app.exceptions import HAError
from app.services.ha_client import HAClient

FIXTURE = Path(__file__).parent / "fixtures" / "ha_states.json"


def _settings() -> Settings:
    return Settings(HA_BASE_URL="http://127.0.0.1:8123", HA_TOKEN="test-token")


def _bulk_states_list() -> list[dict]:
    return list(json.loads(FIXTURE.read_text(encoding="utf-8")).values())


@pytest.mark.asyncio
async def test_get_states_for_bulk_filters_requested_ids():
    client = HAClient(_settings())
    entity_ids = ("switch.hwiya_home", "sensor.hwiya_home_power", "missing.entity")

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = _bulk_states_list()

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=resp)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.ha_client.httpx.AsyncClient", return_value=mock_http):
        result = await client.get_states_for(entity_ids)

    mock_http.get.assert_awaited_once()
    assert mock_http.get.await_args.args[0] == "http://127.0.0.1:8123/api/states"
    assert set(result.keys()) == {"switch.hwiya_home", "sensor.hwiya_home_power"}
    assert result["switch.hwiya_home"]["state"] == "on"


@pytest.mark.asyncio
async def test_get_states_for_empty_tuple_skips_http():
    client = HAClient(_settings())
    with patch("app.services.ha_client.httpx.AsyncClient") as mock_cls:
        assert await client.get_states_for(()) == {}
        mock_cls.assert_not_called()


@pytest.mark.asyncio
async def test_get_states_for_timeout_raises_ha_timeout():
    client = HAClient(_settings())
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.ha_client.httpx.AsyncClient", return_value=mock_http):
        with pytest.raises(HAError) as exc_info:
            await client.get_states_for(("switch.hwiya_home",))

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail["code"] == "ha_timeout"


@pytest.mark.asyncio
async def test_get_states_for_ha_5xx_raises_ha_error():
    client = HAClient(_settings())
    resp = MagicMock()
    resp.status_code = 503
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=resp)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.ha_client.httpx.AsyncClient", return_value=mock_http):
        with pytest.raises(HAError) as exc_info:
            await client.get_states_for(("switch.hwiya_home",))

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["code"] == "ha_error"
