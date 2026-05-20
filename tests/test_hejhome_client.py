import re
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.config import Settings
from app.services.hejhome_client import HejhomeClient


@pytest.mark.asyncio
async def test_oauth_flow_extracts_token():
    settings = Settings(
        HEJHOME_EMAIL="user@example.com",
        HEJHOME_PASSWORD="secret",
    )
    client = HejhomeClient(settings)

    login_resp = MagicMock()
    login_resp.status_code = 200
    login_resp.headers = {"set-cookie": "JSESSIONID=abc123; Path=/"}

    auth_resp = MagicMock()
    auth_resp.status_code = 302
    auth_resp.headers = {"location": "https://square.hej.so/list?code=authcode99"}

    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.json.return_value = {"access_token": "token-xyz"}

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(side_effect=[login_resp, token_resp])
    mock_http.get = AsyncMock(return_value=auth_resp)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.hejhome_client.httpx.AsyncClient", return_value=mock_http):
        token = await client._fetch_access_token()

    assert token == "token-xyz"
    assert mock_http.post.await_count == 2
    assert mock_http.get.await_count == 1


def test_parse_jsession_from_cookie():
    header = "JSESSIONID=deadbeef; Path=/; HttpOnly"
    match = re.search(r"JSESSIONID=([^;]+)", header)
    assert match
    assert match.group(1) == "deadbeef"
