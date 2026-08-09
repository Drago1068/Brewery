import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main() -> None:
    async with engine.connect() as conn:
        schema = (
            await conn.execute(
                text("SELECT value FROM app_meta WHERE key='schema_version'")
            )
        ).scalar()
        print("schema_version", schema)
        exists = (
            await conn.execute(text("SELECT to_regclass('public.brew_events')"))
        ).scalar()
        print("brew_events", exists)
        idx = (
            await conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE indexname='uq_brew_events_correlation_key'"
                )
            )
        ).scalar()
        print("correlation_index", idx)
        count = 0
        if exists:
            count = (
                await conn.execute(text("SELECT count(*) FROM brew_events"))
            ).scalar()
        print("brew_events_count", count)


asyncio.run(main())
