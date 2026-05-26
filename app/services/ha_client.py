from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings
from app.exceptions import HAError

logger = logging.getLogger(__name__)


class HAClient:
    """Single entry point for Home Assistant REST API."""

    def __init__(self, settings: Settings) -> None:
        self._base = settings.ha_base_url.rstrip("/")
        self._token = settings.ha_token
        self._timeout = settings.ha_timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(f"{self._base}/api/", headers=self._headers())
                return resp.status_code == 200
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning("HA ping failed: %s", exc)
            return False

    async def get_state(self, entity_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._base}/api/states/{entity_id}",
                    headers=self._headers(),
                )
            except httpx.TimeoutException:
                raise HAError("Home Assistant request timed out", status_code=504, code="ha_timeout")
            except httpx.RequestError as exc:
                raise HAError(f"Home Assistant unreachable: {exc}", status_code=503)

            if resp.status_code == 404:
                raise HAError(f"Entity not found: {entity_id}", status_code=502, code="ha_error")
            if resp.status_code >= 500:
                raise HAError("Home Assistant server error", status_code=502, code="ha_error")
            if resp.status_code >= 400:
                raise HAError("Home Assistant rejected request", status_code=502, code="ha_error")
            return resp.json()

    async def get_states_for(self, entity_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        """Fetch entities via one GET /api/states; missing IDs are omitted."""
        if not entity_ids:
            return {}

        wanted = frozenset(entity_ids)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._base}/api/states",
                    headers=self._headers(),
                )
            except httpx.TimeoutException:
                raise HAError(
                    "Home Assistant request timed out",
                    status_code=504,
                    code="ha_timeout",
                )
            except httpx.RequestError as exc:
                raise HAError(f"Home Assistant unreachable: {exc}", status_code=503)

            if resp.status_code >= 500:
                raise HAError("Home Assistant server error", status_code=502, code="ha_error")
            if resp.status_code >= 400:
                raise HAError("Home Assistant rejected request", status_code=502, code="ha_error")

            by_id: dict[str, dict[str, Any]] = {}
            for item in resp.json():
                eid = item.get("entity_id")
                if eid in wanted:
                    by_id[eid] = item

            for entity_id in entity_ids:
                if entity_id not in by_id:
                    logger.warning("HA entity missing: %s", entity_id)

            return by_id

    async def call_service(
        self,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        payload = data or {}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    f"{self._base}/api/services/{domain}/{service}",
                    headers=self._headers(),
                    json=payload,
                )
            except httpx.TimeoutException:
                raise HAError(
                    "Home Assistant request timed out",
                    status_code=504,
                    code="ha_timeout",
                )
            except httpx.RequestError as exc:
                raise HAError(f"Home Assistant unreachable: {exc}", status_code=503)

            if resp.status_code >= 500:
                raise HAError("Home Assistant server error", status_code=502, code="ha_error")
            if resp.status_code >= 400:
                raise HAError("Home Assistant rejected service call", status_code=502, code="ha_error")
            if not resp.content:
                return []
            return resp.json()

    async def get_history(
        self,
        entity_id: str,
        *,
        hours: int = 24,
    ) -> list[list[dict[str, Any]]]:
        from datetime import datetime, timedelta, timezone

        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        params = {
            "filter_entity_id": entity_id,
            "minimal_response": "true",
            "no_attributes": "true",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._base}/api/history/period/{start.isoformat()}",
                    headers=self._headers(),
                    params=params,
                )
            except httpx.TimeoutException:
                raise HAError(
                    "Home Assistant request timed out",
                    status_code=504,
                    code="ha_timeout",
                )
            except httpx.RequestError as exc:
                raise HAError(f"Home Assistant unreachable: {exc}", status_code=503)

            if resp.status_code >= 400:
                raise HAError("Home Assistant history request failed", status_code=502, code="ha_error")
            return resp.json()


def get_ha_client(settings: Settings) -> HAClient:
    return HAClient(settings)
