"""SQLAlchemy async engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag_agent.core.config import get_settings
from rag_agent.core.logging import get_logger

logger = get_logger(__name__)

_engine = None
_session_factory = None


def init_engine(database_url: str | None = None) -> None:
    """Initialize the async engine. Called once during app startup."""
    global _engine, _session_factory

    url = database_url or get_settings().database_url
    _engine = create_async_engine(
        url,
        echo=get_settings().debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    logger.info("database.engine_initialized", url=url.split("@")[-1])


async def close_engine() -> None:
    """Dispose the engine. Called during app shutdown."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database.engine_closed")


async def open_session() -> AsyncGenerator[AsyncSession, None]:
    """Open a database session as a dependency.

    Use via ``async for session in open_session():`` for direct usage,
    or ``Depends(open_session)`` in FastAPI route handlers.
    """
    if _session_factory is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")

    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_connection() -> bool:
    """Check if the database is reachable. Returns True/False."""
    try:
        async for session in open_session():
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_connection_detailed() -> tuple[bool, str | None]:
    """Check if the database is reachable. Returns (ok, error_message)."""
    try:
        async for session in open_session():
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, str(e)
