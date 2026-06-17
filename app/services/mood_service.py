from __future__ import annotations

from app.config import Settings
from app.exceptions import MoodRgbNotSupportedError
from app.models.schemas import (
    MoodActionResponse,
    MoodCapabilitiesResponse,
    MoodHsRange,
    MoodMetaResponse,
    MoodStateResponse,
)
from app.services.ha_client import HAClient
from app.services.mood_client import MOOD_ACTIONS, MOOD_COLORS, MoodClient
from app.services.mood_color import PRESET_HS_COLOR, rgb_to_hs


class MoodService:
    """무드등 제어 — HA light 직접(MOOD_LIGHT_ENTITY_ID) 또는 Google Home 경유."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._gh = MoodClient(settings)
        self._ha = HAClient(settings)

    @property
    def ha_direct_enabled(self) -> bool:
        return bool(self._settings.mood_light_entity_id.strip())

    @property
    def _entity_id(self) -> str:
        return self._settings.mood_light_entity_id.strip()

    def capabilities(self) -> MoodCapabilitiesResponse:
        color_modes = ["named"]
        actions = list(MOOD_ACTIONS)
        supports_rgb = False
        supports_hs = False
        supports_state = False
        color_mode: str | None = None
        hs_range: MoodHsRange | None = None
        rgb_range: list[int] | None = None
        color_temperature: bool | None = None

        if self.ha_direct_enabled:
            color_modes.append("hs")
            if "color-rgb" not in actions:
                actions.append("color-rgb")
            if "color-hs" not in actions:
                actions.append("color-hs")
            supports_rgb = True
            supports_hs = True
            supports_state = True
            color_mode = "hs"
            hs_range = MoodHsRange()
            rgb_range = [0, 255]
            color_temperature = False

        return MoodCapabilitiesResponse(
            actions=actions,
            colors=list(MOOD_COLORS),
            color_mode=color_mode,
            hs_range=hs_range,
            rgb_range=rgb_range,
            color_temperature=color_temperature,
            color_modes=color_modes,
            supports_rgb=supports_rgb,
            supports_hex=supports_rgb,
            supports_hs=supports_hs,
            supports_state=supports_state,
        )

    def meta(self) -> MoodMetaResponse:
        if self.ha_direct_enabled:
            return MoodMetaResponse(
                room=self._settings.mood_gh_room,
                device=self._settings.mood_gh_device,
                path="home_assistant",
                control_paths=["home_assistant", "google_assistant_sdk"],
                entity_id=self._entity_id,
                state_readable=True,
            )
        return MoodMetaResponse(
            room=self._settings.mood_gh_room,
            device=self._settings.mood_gh_device,
            path="google_assistant_sdk",
            control_paths=["google_assistant_sdk"],
            state_readable=False,
        )

    async def get_state(self) -> MoodStateResponse:
        if not self.ha_direct_enabled:
            return MoodStateResponse(state_readable=False)

        state = await self._ha.get_state(self._entity_id)
        entity_state = state.get("state")
        on: bool | None = None
        if entity_state == "on":
            on = True
        elif entity_state == "off":
            on = False

        attrs = state.get("attributes", {})
        brightness: int | None = None
        raw_brightness = attrs.get("brightness")
        if raw_brightness is not None:
            brightness = max(1, min(100, round(int(raw_brightness) / 255 * 100)))

        rgb = attrs.get("rgb_color")
        color_hex: str | None = None
        rgb_list: list[int] | None = None
        if isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
            r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
            rgb_list = [r, g, b]
            color_hex = f"#{r:02x}{g:02x}{b:02x}"

        hs_list: list[float] | None = None
        hs = attrs.get("hs_color")
        if isinstance(hs, (list, tuple)) and len(hs) >= 2:
            hs_list = [float(hs[0]), float(hs[1])]

        return MoodStateResponse(
            on=on,
            brightness=brightness,
            color=color_hex,
            rgb=rgb_list,
            hs=hs_list,
            state_readable=True,
            note=None,
        )

    async def _turn_on_hs(self, hue: float, saturation: float) -> None:
        await self._ha.call_service(
            "light",
            "turn_on",
            {
                "entity_id": self._entity_id,
                "hs_color": [hue, saturation],
            },
        )

    async def send_power(self, on: bool) -> MoodActionResponse:
        if self.ha_direct_enabled:
            if on:
                await self._ha.call_service(
                    "light",
                    "turn_on",
                    {"entity_id": self._entity_id},
                )
            else:
                await self._ha.call_service(
                    "light",
                    "turn_off",
                    {"entity_id": self._entity_id},
                )
            return MoodActionResponse(control_path="home_assistant")

        command = await self._gh.send_power(on)
        return MoodActionResponse(command=command, control_path="google_assistant_sdk")

    async def send_brightness(self, percent: int) -> MoodActionResponse:
        if self.ha_direct_enabled:
            await self._ha.call_service(
                "light",
                "turn_on",
                {
                    "entity_id": self._entity_id,
                    "brightness_pct": percent,
                },
            )
            return MoodActionResponse(control_path="home_assistant")

        command = await self._gh.send_brightness(percent)
        return MoodActionResponse(command=command, control_path="google_assistant_sdk")

    async def send_color(self, name: str) -> MoodActionResponse:
        key = name.lower()
        if self.ha_direct_enabled and key in PRESET_HS_COLOR:
            hue, saturation = PRESET_HS_COLOR[key]
            await self._turn_on_hs(hue, saturation)
            return MoodActionResponse(control_path="home_assistant")

        command = await self._gh.send_color(name)
        return MoodActionResponse(command=command, control_path="google_assistant_sdk")

    async def send_color_hs(self, hue: float, saturation: float) -> MoodActionResponse:
        if not self.ha_direct_enabled:
            raise MoodRgbNotSupportedError()

        await self._turn_on_hs(hue, saturation)
        return MoodActionResponse(control_path="home_assistant")

    async def send_color_rgb(self, r: int, g: int, b: int) -> MoodActionResponse:
        if not self.ha_direct_enabled:
            raise MoodRgbNotSupportedError()

        hue, saturation = rgb_to_hs(r, g, b)
        await self._turn_on_hs(hue, saturation)
        return MoodActionResponse(control_path="home_assistant")

    async def send_raw_command(self, command: str) -> MoodActionResponse:
        sent = await self._gh.send_raw_command(command)
        return MoodActionResponse(command=sent, control_path="google_assistant_sdk")
