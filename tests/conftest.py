"""Pytest configuration and fixtures for the test suite."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag_agent.app import create_app
from rag_agent.core.config import Settings
from rag_agent.db.base import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_media_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test media files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        media_path = Path(tmpdir) / "media"
        media_path.mkdir()
        yield media_path


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Database URL for testing."""
    return "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def settings(test_db_url: str, test_media_dir: Path) -> Settings:
    """Test settings."""
    return Settings(
        database_url=test_db_url,
        media_dir=str(test_media_dir),
        max_upload_bytes=10 * 1024 * 1024,  # 10MB
    )


@pytest_asyncio.fixture(scope="session")
async def db_engine(settings: Settings):
    """Database engine for testing."""
    engine = create_async_engine(settings.database_url, echo=False)
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    db_engine,
) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def client(settings: Settings, db_engine, db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client for the FastAPI app."""
    # The db_engine fixture already creates the engine and tables
    # Just pass the settings to create_app
    app = create_app(settings=settings, test_mode=True)

    # Use a transport that calls the app directly
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

