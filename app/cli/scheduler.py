"""Run due strip schedules once (for NAS systemd timer / docker exec)."""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from app.config import get_settings
from app.db.session import async_session_factory, dispose_engine, init_engine
from app.services.schedule_runner import ScheduleRunner


async def _run() -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    init_engine(settings)
    if not settings.strip_configured:
        print(json.dumps({"error": "strip_not_configured"}, ensure_ascii=False))
        return 1

    factory = async_session_factory()
    async with factory() as session:
        runner = ScheduleRunner(settings, session)
        result = await runner.run_due()

    await dispose_engine()
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
