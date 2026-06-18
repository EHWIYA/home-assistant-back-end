from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services.kr_holidays import get_holidays_for_year, is_public_holiday
from app.services.schedule_kst import (
    is_schedule_date_eligible,
    is_schedule_due,
    kst_hhmm,
    preview_schedule_slots,
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


def test_holiday_skip_blocks_execution():
    new_year = datetime(2026, 1, 1, 8, 30, tzinfo=KST)
    assert not is_schedule_due(
        time_kst="08:30",
        days_of_week=[3],
        holiday_mode="skip",
        is_holiday_fn=lambda _d: True,
        now=new_year,
    )


def test_holiday_run_only_on_holiday():
    new_year = datetime(2026, 1, 1, 8, 30, tzinfo=KST)
    assert is_schedule_due(
        time_kst="08:30",
        days_of_week=[],
        holiday_mode="run_only",
        is_holiday_fn=lambda _d: True,
        now=new_year,
    )
    regular = datetime(2026, 1, 2, 8, 30, tzinfo=KST)
    assert not is_schedule_due(
        time_kst="08:30",
        days_of_week=[4],
        holiday_mode="run_only",
        is_holiday_fn=lambda _d: False,
        now=regular,
    )


def test_once_recurrence_specific_date():
    target = datetime(2026, 6, 18, 9, 0, tzinfo=KST)
    assert is_schedule_due(
        time_kst="09:00",
        days_of_week=[],
        recurrence_type="once",
        specific_dates=["2026-06-18"],
        now=target,
    )
    other = datetime(2026, 6, 19, 9, 0, tzinfo=KST)
    assert not is_schedule_due(
        time_kst="09:00",
        days_of_week=[],
        recurrence_type="once",
        specific_dates=["2026-06-18"],
        now=other,
    )


def test_weekly_specific_date_exception():
    saturday = date(2026, 6, 20)
    assert is_schedule_date_eligible(
        target_date=saturday,
        days_of_week=[0, 1, 2, 3, 4],
        specific_dates=["2026-06-20"],
    )


def test_exclude_dates():
    friday = date(2026, 6, 19)
    assert not is_schedule_date_eligible(
        target_date=friday,
        days_of_week=[0, 1, 2, 3, 4],
        exclude_dates=["2026-06-19"],
    )


def test_preview_schedule_slots():
    schedule = {
        "id": "abc",
        "name": "test",
        "time_kst": "08:30",
        "days_of_week": [0, 1, 2, 3, 4],
        "recurrence_type": "weekly",
        "holiday_mode": "ignore",
        "action_type": "channel",
        "channel_number": 1,
    }
    slots = preview_schedule_slots(
        schedule=schedule,
        from_date=date(2026, 6, 15),
        to_date=date(2026, 6, 19),
    )
    assert len(slots) == 5
    assert slots[0]["at_kst"].startswith("2026-06-15T08:30:00")


def test_kr_holidays_2026_has_new_year():
    payload = get_holidays_for_year(2026)
    assert "2026-01-01" in payload["dates"]
    assert is_public_holiday(date(2026, 1, 1))
