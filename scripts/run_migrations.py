"""Run alembic migrations using environment DATABASE_URL."""

import asyncio
import sys
from alembic import context
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine
from sqlalchemy import pool

from rag_agent.db.base import Base
from rag_agent.db.models import SyncLog, TrackedDocument  # noqa: F401

async def run_migrations():
    """Run all pending migrations."""
    import os
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    print(f"Running migrations on: {db_url}")

    engine = create_async_engine(
        db_url,
        poolclass=pool.NullPool,
        echo=True
    )

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    script = ScriptDirectory.from_config(alembic_cfg)

    async with engine.begin() as conn:
        await conn.run_sync(context.configure, script=script, target_metadata=Base.metadata)
        context.run_migrations()

    await engine.dispose()
    print("Migrations completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_migrations())
