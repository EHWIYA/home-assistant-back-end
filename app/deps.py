from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_db_session
from app.exceptions import StripNotConfiguredError, UnauthorizedError
from app.services.schedule_service import ScheduleService
from app.services.strip_service import StripService


def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.iot_api_key:
        raise UnauthorizedError("API key not configured on server")
    if not x_api_key or x_api_key != settings.iot_api_key:
        raise UnauthorizedError()


SettingsDep = Annotated[Settings, Depends(get_settings)]
ApiKeyDep = Annotated[None, Depends(verify_api_key)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_strip_service(
    settings: SettingsDep,
    session: DbSessionDep,
) -> StripService:
    if not settings.strip_configured:
        raise StripNotConfiguredError()
    return StripService(settings, session)


StripServiceDep = Annotated[StripService, Depends(get_strip_service)]


def get_schedule_service(
    settings: SettingsDep,
    session: DbSessionDep,
) -> ScheduleService:
    if not settings.strip_configured:
        raise StripNotConfiguredError()
    return ScheduleService(settings, session)


ScheduleServiceDep = Annotated[ScheduleService, Depends(get_schedule_service)]
