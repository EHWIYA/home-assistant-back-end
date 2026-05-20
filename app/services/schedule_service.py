from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Schedule, ScheduleRun
from app.exceptions import ScheduleNotFoundError, ScheduleValidationError, StripNotConfiguredError
from app.services.strip_service import StripService

_TIME_KST_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _validate_days(days: list[int]) -> list[int]:
    if not days:
        raise ScheduleValidationError("days_of_week must not be empty")
    normalized = sorted(set(days))
    for day in normalized:
        if day < 0 or day > 6:
            raise ScheduleValidationError("days_of_week must be 0-6 (Mon-Sun)")
    return normalized


def _validate_action(
    action_type: str,
    *,
    channel_number: int | None,
    channel_on: bool | None,
    preset_name: str | None,
) -> None:
    if action_type == "channel":
        if channel_number is None or channel_on is None:
            raise ScheduleValidationError("channel action requires channel_number and channel_on")
        if channel_number < 1 or channel_number > 4:
            raise ScheduleValidationError("channel_number must be 1-4")
        return
    if action_type == "preset":
        if not preset_name:
            raise ScheduleValidationError("preset action requires preset_name")
        return
    raise ScheduleValidationError("action_type must be channel or preset")


def schedule_to_dict(schedule: Schedule) -> dict[str, Any]:
    return {
        "id": str(schedule.id),
        "name": schedule.name,
        "enabled": schedule.enabled,
        "action_type": schedule.action_type,
        "channel_number": schedule.channel_number,
        "channel_on": schedule.channel_on,
        "preset_name": schedule.preset_name,
        "time_kst": schedule.time_kst,
        "days_of_week": schedule.days_of_week,
        "created_at": schedule.created_at.isoformat(),
        "updated_at": schedule.updated_at.isoformat(),
    }


def run_to_dict(run: ScheduleRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "schedule_id": str(run.schedule_id),
        "scheduled_at": run.scheduled_at.isoformat(),
        "status": run.status,
        "detail": run.detail,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


class ScheduleService:
    def __init__(self, settings: Settings, session: AsyncSession) -> None:
        if not settings.strip_configured:
            raise StripNotConfiguredError()
        self._settings = settings
        self._session = session
        self._strip = StripService(settings, session)

    async def _device_id(self) -> uuid.UUID:
        device = await self._strip.ensure_device_seed()
        return device.id

    async def list_schedules(self) -> list[dict[str, Any]]:
        device_id = await self._device_id()
        result = await self._session.execute(
            select(Schedule)
            .where(Schedule.device_id == device_id)
            .order_by(Schedule.time_kst, Schedule.name)
        )
        return [schedule_to_dict(row) for row in result.scalars().all()]

    async def get_schedule(self, schedule_id: uuid.UUID) -> dict[str, Any]:
        schedule = await self._get_schedule_model(schedule_id)
        return schedule_to_dict(schedule)

    async def _get_schedule_model(self, schedule_id: uuid.UUID) -> Schedule:
        result = await self._session.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()
        if schedule is None:
            raise ScheduleNotFoundError(str(schedule_id))
        return schedule

    async def create_schedule(self, payload: dict[str, Any]) -> dict[str, Any]:
        time_kst = payload["time_kst"]
        if not _TIME_KST_RE.match(time_kst):
            raise ScheduleValidationError("time_kst must be HH:MM (24h, KST)")

        action_type = payload["action_type"]
        channel_number = payload.get("channel_number")
        channel_on = payload.get("channel_on")
        preset_name = payload.get("preset_name")
        _validate_action(
            action_type,
            channel_number=channel_number,
            channel_on=channel_on,
            preset_name=preset_name,
        )
        days = _validate_days(payload.get("days_of_week", list(range(7))))

        schedule = Schedule(
            device_id=await self._device_id(),
            name=payload["name"],
            enabled=payload.get("enabled", True),
            action_type=action_type,
            channel_number=channel_number,
            channel_on=channel_on,
            preset_name=preset_name,
            time_kst=time_kst,
            days_of_week=days,
        )
        self._session.add(schedule)
        await self._session.commit()
        await self._session.refresh(schedule)
        return schedule_to_dict(schedule)

    async def update_schedule(self, schedule_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
        schedule = await self._get_schedule_model(schedule_id)

        if "time_kst" in payload:
            if not _TIME_KST_RE.match(payload["time_kst"]):
                raise ScheduleValidationError("time_kst must be HH:MM (24h, KST)")
            schedule.time_kst = payload["time_kst"]

        if "days_of_week" in payload:
            schedule.days_of_week = _validate_days(payload["days_of_week"])

        for field in ("name", "enabled", "action_type", "channel_number", "channel_on", "preset_name"):
            if field in payload:
                setattr(schedule, field, payload[field])

        _validate_action(
            schedule.action_type,
            channel_number=schedule.channel_number,
            channel_on=schedule.channel_on,
            preset_name=schedule.preset_name,
        )

        await self._session.commit()
        await self._session.refresh(schedule)
        return schedule_to_dict(schedule)

    async def delete_schedule(self, schedule_id: uuid.UUID) -> None:
        schedule = await self._get_schedule_model(schedule_id)
        await self._session.delete(schedule)
        await self._session.commit()

    async def list_runs(self, schedule_id: uuid.UUID, *, limit: int = 50) -> list[dict[str, Any]]:
        await self._get_schedule_model(schedule_id)
        result = await self._session.execute(
            select(ScheduleRun)
            .where(ScheduleRun.schedule_id == schedule_id)
            .order_by(ScheduleRun.scheduled_at.desc())
            .limit(limit)
        )
        return [run_to_dict(row) for row in result.scalars().all()]

    async def execute_schedule(self, schedule: Schedule, *, source: str) -> None:
        if schedule.action_type == "channel":
            await self._strip.set_channel(
                schedule.channel_number,
                on=bool(schedule.channel_on),
                source=source,
            )
        else:
            await self._strip.apply_preset(schedule.preset_name, source=source)
