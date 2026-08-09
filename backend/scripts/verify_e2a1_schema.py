import asyncio
from sqlalchemy import text
from app.db.session import engine

TABLES = [
    "brew_plans",
    "brew_sessions",
    "brew_stage_occurrences",
    "brew_actions",
    "idempotency_records",
]


async def main() -> None:
    async with engine.connect() as conn:
        schema = (
            await conn.execute(
                text("SELECT value FROM app_meta WHERE key='schema_version'")
            )
        ).scalar()
        print("schema_version", schema)
        for table in TABLES:
            exists = (
                await conn.execute(text(f"SELECT to_regclass('public.{table}')"))
            ).scalar()
            print(table, exists)
        # Partial unique index for one ACTIVE stage
        idx = (
            await conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename='brew_stage_occurrences' "
                    "AND indexname='uq_brew_stage_one_active_per_session'"
                )
            )
        ).scalar()
        print("active_stage_index", idx)


asyncio.run(main())
