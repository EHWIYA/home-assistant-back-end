from __future__ import annotations

import asyncio
import base64
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.constants import (
    HEJHOME_CLIENT_ID,
    HEJHOME_CLIENT_SECRET,
    HEJHOME_OAUTH_REDIRECT_URI,
)
from app.exceptions import HejhomeError

logger = logging.getLogger(__name__)

_token_lock = asyncio.Lock()
_cached_token: str | None = None


class HejhomeClient:
    """square.hej.so REST (PowerStrip2 등). OAuth는 homebridge-hejhome 흐름과 동일."""

    def __init__(self, settings: Settings) -> None:
        self._base = settings.hejhome_base_url.rstrip("/")
        self._email = settings.hejhome_email
        self._password = settings.hejhome_password
        self._timeout = settings.hejhome_timeout_seconds

    @staticmethod
    def _basic_auth_header(user: str, password: str) -> str:
        raw = f"{user}:{password}".encode()
        return f"Basic {base64.b64encode(raw).decode()}"

    @staticmethod
    def _oauth_app_auth() -> str:
        raw = f"{HEJHOME_CLIENT_ID}:{HEJHOME_CLIENT_SECRET}".encode()
        return f"Basic {base64.b64encode(raw).decode()}"

    async def _get_jsession_id(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            f"{self._base}/oauth/login?vendor=shop",
            headers={"authorization": self._basic_auth_header(self._email, self._password)},
        )
        if resp.status_code >= 400:
            raise HejhomeError("Hejhome login failed", code="hejhome_auth_failed")
        set_cookie = resp.headers.get("set-cookie", "")
        match = re.search(r"JSESSIONID=([^;]+)", set_cookie)
        if not match:
            raise HejhomeError("Hejhome login missing session", code="hejhome_auth_failed")
        return match.group(1)

    async def _get_authorization_code(self, client: httpx.AsyncClient, jsession_id: str) -> str:
        username = quote(self._email, safe="")
        cookie = f"username={username}; JSESSIONID={jsession_id}"
        resp = await client.get(
            f"{self._base}/oauth/authorize",
            params={
                "client_id": HEJHOME_CLIENT_ID,
                "redirect_uri": HEJHOME_OAUTH_REDIRECT_URI,
                "response_type": "code",
                "scope": "shop",
            },
            headers={"cookie": cookie},
            follow_redirects=False,
        )
        location = resp.headers.get("location", "")
        match = re.search(r"code=([^&]+)", location)
        if not match:
            raise HejhomeError("Hejhome authorize failed", code="hejhome_auth_failed")
        return match.group(1)

    async def _exchange_token(self, client: httpx.AsyncClient, code: str) -> str:
        resp = await client.post(
            f"{self._base}/oauth/token",
            headers={
                "authorization": self._oauth_app_auth(),
                "content-type": "application/x-www-form-urlencoded",
                "referer": f"{HEJHOME_OAUTH_REDIRECT_URI}?code={code}",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": HEJHOME_CLIENT_ID,
                "redirect_uri": HEJHOME_OAUTH_REDIRECT_URI,
            },
        )
        if resp.status_code >= 400:
            raise HejhomeError("Hejhome token exchange failed", code="hejhome_auth_failed")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise HejhomeError("Hejhome token missing in response", code="hejhome_auth_failed")
        return str(token)

    async def _fetch_access_token(self) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            jsession = await self._get_jsession_id(client)
            code = await self._get_authorization_code(client, jsession)
            return await self._exchange_token(client, code)

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        global _cached_token
        if not force_refresh and _cached_token:
            return _cached_token
        async with _token_lock:
            if not force_refresh and _cached_token:
                return _cached_token
            _cached_token = await self._fetch_access_token()
            return _cached_token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> Any:
        token = await self.get_access_token()
        url = f"{self._base}/{path.lstrip('/')}"
        headers = {
            "authorization": f"Bearer {token}",
            "x-requested-with": "XMLHttpRequest",
            "referer": f"{self._base}/square",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.request(method, url, headers=headers, json=json_body)
            except httpx.TimeoutException:
                raise HejhomeError("Hejhome request timed out", status_code=504, code="hejhome_timeout")
            except httpx.RequestError as exc:
                raise HejhomeError(f"Hejhome unreachable: {exc}", status_code=503)

            if resp.status_code == 401 and retry_auth:
                global _cached_token
                _cached_token = None
                await self.get_access_token(force_refresh=True)
                return await self._request(method, path, json_body=json_body, retry_auth=False)

            if resp.status_code >= 500:
                raise HejhomeError("Hejhome server error", status_code=502)
            if resp.status_code >= 400:
                raise HejhomeError("Hejhome rejected request", status_code=502)

            text = resp.text.strip()
            if not text:
                return None
            return resp.json()

    async def get_device(self, device_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"dashboard/device/{device_id}")
        if not isinstance(data, dict):
            raise HejhomeError("Unexpected Hejhome device response", status_code=502)
        return data

    async def list_devices_state(self, family_id: int) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            f"dashboard/{family_id}/devices-state?scope=shop",
        )
        if isinstance(data, list):
            return data
        return []

    async def control(self, device_id: str, requirements: dict[str, bool]) -> Any:
        return await self._request(
            "POST",
            f"dashboard/control/{device_id}",
            json_body={"requirments": requirements},
        )

    @staticmethod
    def device_state(device: dict[str, Any]) -> dict[str, Any]:
        state = device.get("deviceState")
        return state if isinstance(state, dict) else {}

    @staticmethod
    def channel_power(state: dict[str, Any], power_key: str) -> bool | None:
        value = state.get(power_key)
        if value is None:
            return None
        return bool(value)
