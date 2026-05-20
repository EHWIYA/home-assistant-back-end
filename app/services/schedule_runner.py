from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Schedule, ScheduleRun
from app.exceptions import StripNotConfiguredError
from app.services.schedule_kst import is_schedule_due, kst_now, scheduled_at_utc_for_current_minute
from app.services.schedule_service import ScheduleService, run_to_dict

logger = logging.getLogger(__name__)


class ScheduleRunner:
    def __init__(self, settings: Settings, session: AsyncSession) -> None:
        if not settings.strip_configured:
            raise StripNotConfiguredError()
        self._settings = settings
        self._session = session
        self._schedule_service = ScheduleService(settings, session)

    async def run_due(self, *, now: datetime | None = None) -> dict[str, Any]:
        now_kst = kst_now(now)
        slot_utc = scheduled_at_utc_for_current_minute(now_kst)

        result = await self._session.execute(select(Schedule).where(Schedule.enabled.is_(True)))
        schedules = list(result.scalars().all())

        executed: list[dict[str, Any]] = []
        skipped = 0

        for schedule in schedules:
            if not is_schedule_due(
                time_kst=schedule.time_kst,
                days_of_week=schedule.days_of_week,
                now=now_kst,
            ):
                continue

            existing = await self._session.execute(
                select(ScheduleRun.id).where(
                    ScheduleRun.schedule_id == schedule.id,
                    ScheduleRun.scheduled_at == slot_utc,
                )
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue

            source = f"schedule:{schedule.id}"
            status = "success"
            detail: str | None = None
            try:
                await self._schedule_service.execute_schedule(schedule, source=source)
            except Exception as exc:
                logger.exception("Schedule run failed: %s", schedule.id)
                status = "failed"
                detail = str(exc)[:500]

            run = ScheduleRun(
                schedule_id=schedule.id,
                scheduled_at=slot_utc,
                status=status,
                detail=detail,
            )
            self._session.add(run)
            await self._session.commit()
            executed.append(
                {
                    "schedule_id": str(schedule.id),
                    "schedule_name": schedule.name,
                    "run": run_to_dict(run),
                }
            )

        return {
            "slot_kst": now_kst.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "executed": len(executed),
            "skipped_duplicate": skipped,
            "results": executed,
        }
