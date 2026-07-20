"""Create all database tables."""

import asyncio
import sys
import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from rag_agent.db.base import Base
from rag_agent.db.models import SyncLog, TrackedDocument  # noqa: F401


async def create_all_tables():
    """Create all tables in the database."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    print(f"Creating tables on: {db_url.replace(db_url.split('@')[-1], '***')}")

    engine = create_async_engine(db_url, echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("Tables created successfully!")


if __name__ == "__main__":
    asyncio.run(create_all_tables())
