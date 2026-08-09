"""Verify migration 008 brew_timers schema and app_meta (standalone)."""

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        schema = (
            await conn.execute(
                text("SELECT value FROM app_meta WHERE key='schema_version'")
            )
        ).scalar()
        increment = (
            await conn.execute(text("SELECT value FROM app_meta WHERE key='increment'"))
        ).scalar()
        print("schema_version", schema)
        print("increment", increment)
        exists = (
            await conn.execute(text("SELECT to_regclass('public.brew_timers')"))
        ).scalar()
        print("brew_timers", exists)
        cols = (
            await conn.execute(
                text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'brew_timers'
                    ORDER BY ordinal_position
                    """
                )
            )
        ).scalars().all()
        print("columns", ",".join(cols))
    await engine.dispose()


asyncio.run(main())
