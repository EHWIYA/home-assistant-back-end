from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Schedule, ScheduleRun
from app.exceptions import ScheduleNotFoundError, ScheduleValidationError, StripNotConfiguredError
from app.services.kr_holidays import is_public_holiday
from app.services.schedule_kst import preview_schedule_slots
from app.services.strip_service import StripService

_TIME_KST_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RECURRENCE_TYPES = frozenset({"weekly", "once", "daily"})
_HOLIDAY_MODES = frozenset({"ignore", "skip", "run_only"})


def _validate_days(days: list[int], *, recurrence_type: str) -> list[int]:
    if recurrence_type == "once" and not days:
        return []
    if not days:
        raise ScheduleValidationError("days_of_week must not be empty")
    normalized = sorted(set(days))
    for day in normalized:
        if day < 0 or day > 6:
            raise ScheduleValidationError("days_of_week must be 0-6 (Mon-Sun)")
    return normalized


def _validate_dates(field_name: str, dates: list[str] | None) -> list[str]:
    if not dates:
        return []
    normalized = sorted(set(dates))
    for value in normalized:
        if not _DATE_RE.match(value):
            raise ScheduleValidationError(f"{field_name} must be YYYY-MM-DD")
    return normalized


def _validate_recurrence(recurrence_type: str) -> str:
    if recurrence_type not in _RECURRENCE_TYPES:
        raise ScheduleValidationError("recurrence_type must be weekly, once, or daily")
    return recurrence_type


def _validate_holiday_mode(mode: str) -> str:
    if mode not in _HOLIDAY_MODES:
        raise ScheduleValidationError("holiday_mode must be ignore, skip, or run_only")
    return mode


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
        "recurrence_type": schedule.recurrence_type,
        "specific_dates": schedule.specific_dates or [],
        "exclude_dates": schedule.exclude_dates or [],
        "holiday_mode": schedule.holiday_mode,
        "include_substitute": schedule.include_substitute,
        "created_at": schedule.created_at.isoformat(),
        "updated_at": schedule.updated_at.isoformat(),
    }


def run_to_dict(run: ScheduleRun) -> dict[str, Any]:
    success = run.status == "success"
    return {
        "id": str(run.id),
        "schedule_id": str(run.schedule_id),
        "scheduled_at": run.scheduled_at.isoformat(),
        "status": run.status,
        "executed_at": run.scheduled_at.isoformat(),
        "success": success,
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

    def _holiday_checker(self, include_substitute: bool):
        data_dir = self._settings.kr_holidays_dir

        def _check(target: date) -> bool:
            return is_public_holiday(
                target,
                include_substitute=include_substitute,
                data_dir=data_dir,
            )

        return _check

    async def _device_id(self) -> uuid.UUID:
        device = await self._strip.ensure_device_seed()
        return device.id

    async def list_schedules(self, *, channel: int | None = None) -> list[dict[str, Any]]:
        device_id = await self._device_id()
        stmt = (
            select(Schedule)
            .where(Schedule.device_id == device_id)
            .order_by(Schedule.time_kst, Schedule.name)
        )
        if channel is not None:
            if channel < 1 or channel > 4:
                raise ScheduleValidationError("channel must be 1-4")
            stmt = stmt.where(
                Schedule.action_type == "channel",
                Schedule.channel_number == channel,
            )
        result = await self._session.execute(stmt)
        return [schedule_to_dict(row) for row in result.scalars().all()]

    async def preview_schedules(
        self,
        *,
        from_date: date,
        to_date: date,
        channel: int | None = None,
    ) -> list[dict[str, Any]]:
        schedules = await self.list_schedules(channel=channel)
        slots: list[dict[str, Any]] = []
        for item in schedules:
            if not item["enabled"]:
                continue
            checker = self._holiday_checker(bool(item.get("include_substitute", True)))
            slots.extend(
                preview_schedule_slots(
                    schedule=item,
                    from_date=from_date,
                    to_date=to_date,
                    is_holiday_fn=checker,
                )
            )
        slots.sort(key=lambda row: row["at_kst"])
        return slots

    async def get_schedule(self, schedule_id: uuid.UUID) -> dict[str, Any]:
        schedule = await self._get_schedule_model(schedule_id)
        return schedule_to_dict(schedule)

    async def _get_schedule_model(self, schedule_id: uuid.UUID) -> Schedule:
        result = await self._session.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()
        if schedule is None:
            raise ScheduleNotFoundError(str(schedule_id))
        return schedule

    def _apply_schedule_fields(self, schedule: Schedule, payload: dict[str, Any]) -> None:
        recurrence_type = payload.get("recurrence_type", schedule.recurrence_type)
        recurrence_type = _validate_recurrence(recurrence_type)
        schedule.recurrence_type = recurrence_type

        if "time_kst" in payload:
            if not _TIME_KST_RE.match(payload["time_kst"]):
                raise ScheduleValidationError("time_kst must be HH:MM (24h, KST)")
            schedule.time_kst = payload["time_kst"]

        if "days_of_week" in payload:
            schedule.days_of_week = _validate_days(payload["days_of_week"], recurrence_type=recurrence_type)
        elif recurrence_type == "once" and not schedule.days_of_week:
            schedule.days_of_week = []

        if "specific_dates" in payload:
            schedule.specific_dates = _validate_dates("specific_dates", payload["specific_dates"])
        if "exclude_dates" in payload:
            schedule.exclude_dates = _validate_dates("exclude_dates", payload["exclude_dates"])
        if "holiday_mode" in payload:
            schedule.holiday_mode = _validate_holiday_mode(payload["holiday_mode"])
        if "include_substitute" in payload:
            schedule.include_substitute = bool(payload["include_substitute"])

        for field in ("name", "enabled", "action_type", "channel_number", "channel_on", "preset_name"):
            if field in payload:
                setattr(schedule, field, payload[field])

        if recurrence_type == "once" and not schedule.specific_dates:
            raise ScheduleValidationError("once recurrence requires specific_dates")

        _validate_action(
            schedule.action_type,
            channel_number=schedule.channel_number,
            channel_on=schedule.channel_on,
            preset_name=schedule.preset_name,
        )

    async def create_schedule(self, payload: dict[str, Any]) -> dict[str, Any]:
        recurrence_type = _validate_recurrence(payload.get("recurrence_type", "weekly"))
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
        days = _validate_days(payload.get("days_of_week", list(range(7))), recurrence_type=recurrence_type)
        specific_dates = _validate_dates("specific_dates", payload.get("specific_dates"))
        exclude_dates = _validate_dates("exclude_dates", payload.get("exclude_dates"))
        holiday_mode = _validate_holiday_mode(payload.get("holiday_mode", "ignore"))

        if recurrence_type == "once" and not specific_dates:
            raise ScheduleValidationError("once recurrence requires specific_dates")

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
            recurrence_type=recurrence_type,
            specific_dates=specific_dates,
            exclude_dates=exclude_dates,
            holiday_mode=holiday_mode,
            include_substitute=payload.get("include_substitute", True),
        )
        self._session.add(schedule)
        await self._session.commit()
        await self._session.refresh(schedule)
        return schedule_to_dict(schedule)

    async def update_schedule(self, schedule_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
        schedule = await self._get_schedule_model(schedule_id)
        self._apply_schedule_fields(schedule, payload)
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
