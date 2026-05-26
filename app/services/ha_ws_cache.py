from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

import websockets
from websockets.asyncio.client import connect as ws_connect

from app.config import Settings
from app.constants import STATUS_ENTITY_IDS
from app.models.schemas import StatusResponse
from app.services.status_builder import build_status_from_states

logger = logging.getLogger(__name__)

RECONNECT_MIN_SECONDS = 2.0
RECONNECT_MAX_SECONDS = 30.0
WS_RECV_TIMEOUT_SECONDS = 90.0


def ha_websocket_url(ha_base_url: str) -> str:
    parsed = urlparse(ha_base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, "/api/websocket", "", "", ""))


class HAStateCache:
    """In-memory HA entity cache fed by WebSocket state_changed events."""

    _instance: HAStateCache | None = None

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._connected = False
        self._snapshot_ready = False
        self._subscribers: list[asyncio.Queue[str | None]] = []
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_broadcast_json: str | None = None
        self._settings: Settings | None = None

    @classmethod
    def get(cls) -> HAStateCache:
        if cls._instance is None:
            cls._instance = HAStateCache()
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> None:
        cls._instance = None

    @property
    def use_cache(self) -> bool:
        return self._connected and self._snapshot_ready

    def get_states_copy(self) -> dict[str, dict[str, Any]]:
        return dict(self._states)

    def build_status(self, settings: Settings) -> StatusResponse:
        return build_status_from_states(
            self.get_states_copy(),
            ac_power_threshold_w=settings.ac_power_threshold_w,
            pc_power_threshold_w=settings.pc_power_threshold_w,
        )

    def apply_state_dict(self, entity_id: str, state: dict[str, Any]) -> bool:
        if entity_id not in STATUS_ENTITY_IDS:
            return False
        self._states[entity_id] = state
        return True

    def apply_get_states_result(self, states: list[dict[str, Any]]) -> None:
        wanted = frozenset(STATUS_ENTITY_IDS)
        for item in states:
            eid = item.get("entity_id")
            if eid in wanted:
                self._states[eid] = item

    def subscribe(self) -> asyncio.Queue[str | None]:
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str | None]) -> None:
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    def start(self, settings: Settings) -> None:
        self._settings = settings
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run_loop(), name="ha-ws-cache")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._connected = False
        self._snapshot_ready = False

    def _maybe_broadcast(self, settings: Settings, *, force: bool = False) -> None:
        payload = self.build_status(settings).model_dump_json()
        if not force and payload == self._last_broadcast_json:
            return
        self._last_broadcast_json = payload
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("SSE subscriber queue full, dropping update")

    async def _run_loop(self) -> None:
        settings = self._settings
        if settings is None or not settings.ha_token:
            logger.warning("HA WebSocket cache disabled: HA_TOKEN not set")
            return

        backoff = RECONNECT_MIN_SECONDS
        while not self._stop.is_set():
            try:
                await self._session(settings)
                backoff = RECONNECT_MIN_SECONDS
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("HA WebSocket session ended: %s", exc)
            self._connected = False
            self._snapshot_ready = False
            if self._stop.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)

    async def _session(self, settings: Settings) -> None:
        url = ha_websocket_url(settings.ha_base_url)
        timeout = settings.ha_timeout_seconds
        wanted = frozenset(STATUS_ENTITY_IDS)

        async with ws_connect(url, open_timeout=timeout) as ws:
            await self._authenticate(ws, settings, timeout)
            self._connected = True

            subscribe_id = 1
            get_states_id = 2
            await ws.send(
                json.dumps(
                    {
                        "id": subscribe_id,
                        "type": "subscribe_events",
                        "event_type": "state_changed",
                    }
                )
            )
            await ws.send(json.dumps({"id": get_states_id, "type": "get_states"}))

            while not self._stop.is_set():
                raw = await asyncio.wait_for(ws.recv(), timeout=WS_RECV_TIMEOUT_SECONDS)
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "event":
                    event = msg.get("event") or {}
                    if event.get("event_type") != "state_changed":
                        continue
                    data = event.get("data") or {}
                    eid = data.get("entity_id")
                    new_state = data.get("new_state")
                    if eid in wanted and isinstance(new_state, dict):
                        self._states[eid] = new_state
                        if self._snapshot_ready and self._settings is not None:
                            self._maybe_broadcast(self._settings)
                    continue

                if msg_type != "result" or not msg.get("success"):
                    if msg_type == "result" and not msg.get("success"):
                        logger.warning("HA WebSocket command failed: %s", msg)
                    continue

                if msg.get("id") == get_states_id:
                    result = msg.get("result")
                    if isinstance(result, list):
                        self.apply_get_states_result(result)
                    self._snapshot_ready = True
                    if self._settings is not None:
                        self._maybe_broadcast(self._settings, force=True)

    async def _authenticate(
        self,
        ws: Any,
        settings: Settings,
        timeout: float,
    ) -> None:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") != "auth_required":
            raise RuntimeError(f"unexpected HA WS handshake: {msg.get('type')}")

        await ws.send(json.dumps({"type": "auth", "access_token": settings.ha_token}))
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") != "auth_ok":
            raise RuntimeError("HA WebSocket authentication failed")


def get_ha_state_cache() -> HAStateCache:
    return HAStateCache.get()
