"""Verify migration 009 fermentation_handoffs schema and app_meta."""

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
            await conn.execute(
                text("SELECT to_regclass('public.fermentation_handoffs')")
            )
        ).scalar()
        print("fermentation_handoffs", exists)
        timers = (
            await conn.execute(text("SELECT to_regclass('public.brew_timers')"))
        ).scalar()
        print("brew_timers", timers)
    await engine.dispose()


asyncio.run(main())
