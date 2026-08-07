"""Async engine and session lifecycle.

One engine per process, created lazily so importing `app.db` in a unit test
does not open a socket. A statement timeout is applied at connect time: a
runaway query in a request handler should fail fast and surface as a 500 with
a correlation id, not hold a connection until the pool starves.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            str(settings.database_url),
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            # Recycle below the typical 5-minute proxy idle timeout so we never
            # hand out a connection the network has already dropped.
            pool_recycle=280,
            echo=False,
            connect_args={
                "server_settings": {
                    "application_name": settings.service_name,
                    "statement_timeout": str(settings.db_statement_timeout_ms),
                }
            },
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one transaction per request.

    Commit on success, roll back on any exception. Handlers therefore never
    call `commit()` themselves, which is what keeps a partially-written audit
    trail impossible.
    """
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Close the pool on shutdown so containers stop without hanging."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
