from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings
from app.exceptions import MoodError

logger = logging.getLogger(__name__)

COLOR_KO: dict[str, str] = {
    "red": "빨간색",
    "blue": "파란색",
    "green": "초록색",
    "yellow": "노란색",
    "purple": "보라색",
    "white": "흰색",
    "warm": "따뜻한 색",
    "cool": "차가운 색",
}

MOOD_COLORS = tuple(COLOR_KO.keys()) + ("rainbow",)
MOOD_ACTIONS = ("power", "brightness", "color", "color-temperature", "command")


def phrase(room: str, device: str, text: str) -> str:
    return f"{room} {device} {text}".strip()


def build_command(
    *,
    room: str,
    device: str,
    action: str,
    percent: int | None = None,
    color: str | None = None,
    raw: str | None = None,
) -> str:
    if action == "raw":
        if not raw:
            raise ValueError("raw command required")
        return raw
    if action == "on":
        return phrase(room, device, "켜줘")
    if action == "off":
        return phrase(room, device, "꺼줘")
    if action == "brightness":
        if percent is None:
            raise ValueError("percent required")
        pct = max(1, min(100, int(percent)))
        return phrase(room, device, f"밝기 {pct}%로 해줘")
    if action == "color":
        if not color:
            raise ValueError("color required")
        key = color.lower()
        if key in COLOR_KO:
            return phrase(room, device, f"{COLOR_KO[key]}으로 해줘")
        if key == "rainbow":
            return phrase(room, device, "무지개 모드 켜줘")
        return phrase(room, device, f"{color}으로 해줘")
    raise ValueError(f"unknown action: {action}")


class MoodClient:
    """Google Home 경유 무드등 제어 (HA google_assistant_sdk.send_text_command)."""

    def __init__(self, settings: Settings) -> None:
        self._base = settings.ha_base_url.rstrip("/")
        self._token = settings.ha_token
        self._timeout = settings.mood_gh_timeout_seconds
        self._room = settings.mood_gh_room
        self._device = settings.mood_gh_device

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def check_integration(self) -> bool:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._base}/api/config/config_entries/entry",
                    headers=self._headers(),
                )
            except httpx.TimeoutException:
                raise MoodError(
                    "Home Assistant request timed out",
                    status_code=504,
                    code="ha_timeout",
                )
            except httpx.RequestError as exc:
                raise MoodError(
                    f"Home Assistant unreachable: {exc}",
                    status_code=503,
                    code="ha_unreachable",
                )

            if resp.status_code >= 400:
                raise MoodError(
                    "Home Assistant rejected config request",
                    status_code=502,
                    code="ha_error",
                )

            entries = resp.json()
            return any(e.get("domain") == "google_assistant_sdk" for e in entries)

    async def send_text_command(self, command: str) -> list[dict[str, Any]]:
        if not await self.check_integration():
            raise MoodError(
                "google_assistant_sdk integration not loaded",
                status_code=503,
                code="mood_integration_missing",
            )

        url = f"{self._base}/api/services/google_assistant_sdk/send_text_command?return_response"
        body = {"command": [command]}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    url,
                    headers=self._headers(),
                    json=body,
                )
            except httpx.TimeoutException:
                raise MoodError(
                    "Home Assistant request timed out",
                    status_code=504,
                    code="ha_timeout",
                )
            except httpx.RequestError as exc:
                raise MoodError(
                    f"Home Assistant unreachable: {exc}",
                    status_code=503,
                    code="ha_unreachable",
                )

            if resp.status_code >= 500:
                raise MoodError(
                    "Home Assistant server error",
                    status_code=502,
                    code="mood_command_failed",
                )
            if resp.status_code >= 400:
                detail = resp.text
                reauth = "reauth" in detail.lower() or "oauth" in detail.lower()
                raise MoodError(
                    "Google Assistant command failed",
                    status_code=502,
                    code="mood_command_failed",
                    reauth_required=reauth,
                )

            if not resp.content:
                return []
            return resp.json()

    def build_power_command(self, on: bool) -> str:
        return build_command(
            room=self._room,
            device=self._device,
            action="on" if on else "off",
        )

    def build_brightness_command(self, percent: int) -> str:
        return build_command(
            room=self._room,
            device=self._device,
            action="brightness",
            percent=percent,
        )

    def build_color_command(self, name: str) -> str:
        return build_command(
            room=self._room,
            device=self._device,
            action="color",
            color=name,
        )

    async def send_power(self, on: bool) -> str:
        command = self.build_power_command(on)
        await self.send_text_command(command)
        return command

    async def send_brightness(self, percent: int) -> str:
        command = self.build_brightness_command(percent)
        await self.send_text_command(command)
        return command

    async def send_color(self, name: str) -> str:
        command = self.build_color_command(name)
        await self.send_text_command(command)
        return command

    async def send_raw_command(self, command: str) -> str:
        await self.send_text_command(command)
        return command
