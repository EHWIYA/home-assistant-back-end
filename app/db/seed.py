from __future__ import annotations

import logging

from sqlalchemy import select

from app.config import Settings
from app.db.models import Device
from app.db.session import async_session_factory
from app.services.strip_service import StripService

logger = logging.getLogger(__name__)


async def seed_strip_device(settings: Settings) -> None:
    if not settings.strip_configured:
        return
    factory = async_session_factory()
    async with factory() as session:
        existing = await session.execute(
            select(Device).where(Device.external_id == settings.hejhome_strip_id)
        )
        if existing.scalar_one_or_none():
            return
        service = StripService(settings, session)
        await service.ensure_device_seed()
        logger.info("Seeded strip device %s", settings.hejhome_strip_id)
