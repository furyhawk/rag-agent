"""FastAPI dependency injection providers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from rag_agent.core.config import Settings, get_settings
from rag_agent.core.database import open_session
from rag_agent.core.valkey import get_valkey


def get_settings_dep() -> Settings:
    """Provide application settings."""
    return get_settings()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session."""
    async with open_session() as session:
        yield session


def get_redis():
    """Provide the Valkey client."""
    return get_valkey()


# Type aliases for cleaner route signatures
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
RedisDep = Annotated[object, Depends(get_redis)]
