from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RecurrenceType = str  # weekly | once | daily
HolidayMode = str  # ignore | skip | run_only


def to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def kst_now(now: datetime | None = None) -> datetime:
    return to_kst(now or datetime.now(timezone.utc))


def kst_minute_start(now: datetime | None = None) -> datetime:
    kst = kst_now(now)
    return kst.replace(second=0, microsecond=0)


def kst_hhmm(now: datetime | None = None) -> str:
    return kst_minute_start(now).strftime("%H:%M")


def kst_date_str(now: datetime | None = None) -> str:
    return kst_minute_start(now).date().isoformat()


def _normalize_dates(dates: list[str] | None) -> set[str]:
    if not dates:
        return set()
    out: set[str] = set()
    for value in dates:
        if not _DATE_RE.match(value):
            raise ValueError(f"invalid date: {value}")
        out.add(value)
    return out


def is_schedule_date_eligible(
    *,
    target_date: date,
    recurrence_type: RecurrenceType = "weekly",
    days_of_week: list[int],
    specific_dates: list[str] | None = None,
    exclude_dates: list[str] | None = None,
    holiday_mode: HolidayMode = "ignore",
    include_substitute: bool = True,
    is_holiday_fn: Callable[[date], bool] | None = None,
) -> bool:
    date_str = target_date.isoformat()
    if date_str in _normalize_dates(exclude_dates):
        return False

    is_holiday = is_holiday_fn(target_date) if is_holiday_fn else False

    if holiday_mode == "skip" and is_holiday:
        return False
    if holiday_mode == "run_only":
        return is_holiday

    specific = _normalize_dates(specific_dates)
    if recurrence_type == "once":
        return date_str in specific

    weekday_match = target_date.weekday() in days_of_week
    if recurrence_type == "daily":
        return weekday_match or date_str in specific
    return weekday_match or date_str in specific


def is_schedule_due(
    *,
    time_kst: str,
    days_of_week: list[int],
    now: datetime | None = None,
    recurrence_type: RecurrenceType = "weekly",
    specific_dates: list[str] | None = None,
    exclude_dates: list[str] | None = None,
    holiday_mode: HolidayMode = "ignore",
    include_substitute: bool = True,
    is_holiday_fn: Callable[[date], bool] | None = None,
) -> bool:
    """time_kst: HH:MM, days_of_week: 0=Mon .. 6=Sun (Python weekday)."""
    kst = kst_minute_start(now)
    if kst_hhmm(kst) != time_kst:
        return False
    return is_schedule_date_eligible(
        target_date=kst.date(),
        recurrence_type=recurrence_type,
        days_of_week=days_of_week,
        specific_dates=specific_dates,
        exclude_dates=exclude_dates,
        holiday_mode=holiday_mode,
        include_substitute=include_substitute,
        is_holiday_fn=is_holiday_fn,
    )


def scheduled_at_utc_for_current_minute(now: datetime | None = None) -> datetime:
    return kst_minute_start(now).astimezone(timezone.utc)


def preview_schedule_slots(
    *,
    schedule: dict[str, Any],
    from_date: date,
    to_date: date,
    is_holiday_fn: Callable[[date], bool] | None = None,
) -> list[dict[str, Any]]:
    if from_date > to_date:
        return []

    hour, minute = (int(part) for part in schedule["time_kst"].split(":"))
    slots: list[dict[str, Any]] = []
    current = from_date
    while current <= to_date:
        if is_schedule_date_eligible(
            target_date=current,
            recurrence_type=schedule.get("recurrence_type", "weekly"),
            days_of_week=schedule["days_of_week"],
            specific_dates=schedule.get("specific_dates"),
            exclude_dates=schedule.get("exclude_dates"),
            holiday_mode=schedule.get("holiday_mode", "ignore"),
            include_substitute=schedule.get("include_substitute", True),
            is_holiday_fn=is_holiday_fn,
        ):
            at_kst = datetime(
                current.year,
                current.month,
                current.day,
                hour,
                minute,
                tzinfo=KST,
            )
            slots.append(
                {
                    "schedule_id": schedule["id"],
                    "schedule_name": schedule["name"],
                    "at_kst": at_kst.isoformat(),
                    "channel_number": schedule.get("channel_number"),
                    "action_type": schedule["action_type"],
                }
            )
        current += timedelta(days=1)
    return slots
