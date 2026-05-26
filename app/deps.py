from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_db_session
from app.exceptions import StripNotConfiguredError, UnauthorizedError
from app.services.schedule_service import ScheduleService
from app.services.strip_service import StripService


def _check_api_key(provided: str | None, settings: Settings) -> None:
    if not settings.iot_api_key:
        raise UnauthorizedError("API key not configured on server")
    if not provided or provided != settings.iot_api_key:
        raise UnauthorizedError()


def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    _check_api_key(x_api_key, settings)


def verify_api_key_header_or_query(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    api_key: Annotated[str | None, Query(alias="api_key")] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """X-API-Key header or ?api_key= for EventSource (no custom headers)."""
    _check_api_key(x_api_key or api_key, settings)


SettingsDep = Annotated[Settings, Depends(get_settings)]
ApiKeyDep = Annotated[None, Depends(verify_api_key)]
ApiKeyHeaderOrQueryDep = Annotated[None, Depends(verify_api_key_header_or_query)]
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
