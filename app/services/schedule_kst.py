from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


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


def is_schedule_due(
    *,
    time_kst: str,
    days_of_week: list[int],
    now: datetime | None = None,
) -> bool:
    """time_kst: HH:MM, days_of_week: 0=Mon .. 6=Sun (Python weekday)."""
    kst = kst_minute_start(now)
    if kst_hhmm(kst) != time_kst:
        return False
    return kst.weekday() in days_of_week


def scheduled_at_utc_for_current_minute(now: datetime | None = None) -> datetime:
    return kst_minute_start(now).astimezone(timezone.utc)
