from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.constants import HEJHOME_DEVICE_TYPE_STRIP, STRIP_CHANNEL_POWER_KEYS
from app.db.models import Channel, ControlAudit, Device, StripPreset
from app.exceptions import HejhomeError, StripNotConfiguredError
from app.services.hejhome_client import HejhomeClient


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StripService:
    def __init__(self, settings: Settings, session: AsyncSession) -> None:
        if not settings.strip_configured:
            raise StripNotConfiguredError()
        self._settings = settings
        self._session = session
        self._hej = HejhomeClient(settings)

    async def ensure_device_seed(self) -> Device:
        result = await self._session.execute(
            select(Device).where(Device.external_id == self._settings.hejhome_strip_id)
        )
        device = result.scalar_one_or_none()
        if device:
            return device

        device = Device(
            external_id=self._settings.hejhome_strip_id,
            device_type=HEJHOME_DEVICE_TYPE_STRIP,
            name="자취방 멀티탭",
            family_id=self._settings.hejhome_family_id,
        )
        self._session.add(device)
        await self._session.flush()

        for idx, power_key in enumerate(STRIP_CHANNEL_POWER_KEYS[: self._settings.strip_channel_count], start=1):
            self._session.add(
                Channel(
                    device_id=device.id,
                    channel_number=idx,
                    power_key=power_key,
                )
            )
        await self._session.commit()
        await self._session.refresh(device)
        return device

    async def _get_device_with_channels(self) -> tuple[Device, list[Channel]]:
        device = await self.ensure_device_seed()
        result = await self._session.execute(
            select(Channel)
            .where(Channel.device_id == device.id)
            .order_by(Channel.channel_number)
        )
        channels = list(result.scalars().all())
        return device, channels

    async def _device_online(self, device: Device) -> bool | None:
        items = await self._hej.list_devices_state(device.family_id or self._settings.hejhome_family_id)
        for item in items:
            if item.get("id") == device.external_id:
                return bool(item.get("online"))
        return None

    async def get_state(self) -> dict:
        device, channels = await self._get_device_with_channels()
        raw = await self._hej.get_device(device.external_id)
        state = HejhomeClient.device_state(raw)
        online = raw.get("online")
        if online is None:
            online = await self._device_online(device)

        channel_states = []
        for ch in channels:
            channel_states.append(
                {
                    "channel": ch.channel_number,
                    "on": HejhomeClient.channel_power(state, ch.power_key),
                    "label": ch.label,
                }
            )

        return {
            "device_id": device.external_id,
            "online": online,
            "channels": channel_states,
            "updated_at": _utc_now_iso(),
        }

    async def set_channel(self, channel_number: int, *, on: bool, source: str = "api") -> dict:
        device, channels = await self._get_device_with_channels()
        channel = next((c for c in channels if c.channel_number == channel_number), None)
        if channel is None:
            raise HejhomeError(f"Invalid channel: {channel_number}", status_code=400, code="invalid_channel")

        action = "on" if on else "off"
        audit = ControlAudit(
            device_id=device.id,
            channel_number=channel_number,
            action=action,
            source=source,
            success=False,
        )
        self._session.add(audit)

        try:
            await self._hej.control(device.external_id, {channel.power_key: on})
            audit.success = True
            await self._session.commit()
        except Exception as exc:
            audit.detail = str(exc)[:500]
            await self._session.commit()
            raise

        return await self.get_state()

    async def apply_preset(self, name: str, *, source: str | None = None) -> dict:
        result = await self._session.execute(select(StripPreset).where(StripPreset.name == name))
        preset = result.scalar_one_or_none()
        if preset is None:
            raise HejhomeError(f"Preset not found: {name}", status_code=404, code="preset_not_found")

        device, channels = await self._get_device_with_channels()
        requirements: dict[str, bool] = {}
        for ch in channels:
            key = str(ch.channel_number)
            if key in preset.channels:
                requirements[ch.power_key] = bool(preset.channels[key])
            elif ch.power_key in preset.channels:
                requirements[ch.power_key] = bool(preset.channels[ch.power_key])

        if not requirements:
            raise HejhomeError("Preset has no channel mappings", status_code=400, code="invalid_preset")

        audit = ControlAudit(
            device_id=device.id,
            channel_number=None,
            action="preset",
            source=source or f"preset:{name}",
            success=False,
        )
        self._session.add(audit)
        try:
            await self._hej.control(device.external_id, requirements)
            audit.success = True
            await self._session.commit()
        except Exception as exc:
            audit.detail = str(exc)[:500]
            await self._session.commit()
            raise

        return await self.get_state()
