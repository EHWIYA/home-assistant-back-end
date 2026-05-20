from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.schedule_kst import (
    is_schedule_due,
    kst_hhmm,
    scheduled_at_utc_for_current_minute,
)

KST = ZoneInfo("Asia/Seoul")


def test_is_schedule_due_matching_monday_0830():
    now = datetime(2026, 5, 18, 8, 30, tzinfo=KST)  # Monday
    assert is_schedule_due(time_kst="08:30", days_of_week=[0], now=now)


def test_is_schedule_due_wrong_day():
    now = datetime(2026, 5, 18, 8, 30, tzinfo=KST)  # Monday
    assert not is_schedule_due(time_kst="08:30", days_of_week=[6], now=now)


def test_is_schedule_due_wrong_minute():
    now = datetime(2026, 5, 18, 8, 31, tzinfo=KST)
    assert not is_schedule_due(time_kst="08:30", days_of_week=[0], now=now)


def test_scheduled_at_utc_from_kst_minute():
    from datetime import timezone

    now = datetime(2026, 5, 18, 8, 30, 45, tzinfo=KST)
    utc = scheduled_at_utc_for_current_minute(now)
    assert utc == datetime(2026, 5, 17, 23, 30, tzinfo=timezone.utc)
    assert kst_hhmm(now) == "08:30"
