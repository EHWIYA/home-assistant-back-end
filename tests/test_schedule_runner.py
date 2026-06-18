import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.services.schedule_runner import ScheduleRunner

KST = ZoneInfo("Asia/Seoul")


def _schedule(**kwargs):
    s = MagicMock()
    s.id = kwargs.get("id", uuid.uuid4())
    s.name = kwargs.get("name", "test")
    s.time_kst = kwargs.get("time_kst", "08:30")
    s.days_of_week = kwargs.get("days_of_week", [0])
    s.recurrence_type = kwargs.get("recurrence_type", "weekly")
    s.specific_dates = kwargs.get("specific_dates", [])
    s.exclude_dates = kwargs.get("exclude_dates", [])
    s.holiday_mode = kwargs.get("holiday_mode", "ignore")
    s.include_substitute = kwargs.get("include_substitute", True)
    s.enabled = True
    s.action_type = "channel"
    s.channel_number = 1
    s.channel_on = True
    s.preset_name = None
    return s


@pytest.mark.asyncio
async def test_run_due_executes_matching_schedule():
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://u@localhost/db",
        HEJHOME_EMAIL="a@b.com",
        HEJHOME_PASSWORD="x",
        HEJHOME_STRIP_ID="strip1",
        HEJHOME_FAMILY_ID=1,
    )
    session = AsyncMock()
    monday_0830 = datetime(2026, 5, 18, 8, 30, tzinfo=KST)

    sched = _schedule()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [sched]

    existing_mock = MagicMock()
    existing_mock.scalar_one_or_none.return_value = None

    session.execute = AsyncMock(side_effect=[result_mock, existing_mock])
    session.add = MagicMock()
    session.commit = AsyncMock()

    runner = ScheduleRunner(settings, session)
    with patch.object(runner._schedule_service, "execute_schedule", AsyncMock()) as execute:
        with patch("app.services.schedule_runner.kst_now", return_value=monday_0830):
            with patch(
                "app.services.schedule_runner.scheduled_at_utc_for_current_minute",
                return_value=datetime(2026, 5, 17, 23, 30, tzinfo=datetime.now().astimezone().tzinfo),
            ):
                out = await runner.run_due(now=monday_0830)

    assert out["executed"] == 1
    execute.assert_awaited_once()
