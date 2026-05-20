from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> AsyncEngine | None:
    global _engine, _async_session_factory
    if not settings.database_url:
        return None
    _engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )
    _async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine | None:
    return _engine


async def dispose_engine() -> None:
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _async_session_factory = None


def async_session_factory() -> async_sessionmaker[AsyncSession]:
    if _async_session_factory is None:
        raise RuntimeError("Database engine not initialized")
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    from app.config import get_settings
    from app.exceptions import StripNotConfiguredError

    settings = get_settings()
    if not settings.database_url:
        raise StripNotConfiguredError()
    factory = async_session_factory()
    async with factory() as session:
        yield session
