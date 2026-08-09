import asyncio

from sqlalchemy import text

from app.db.session import engine

TABLES = [
    "measurement_definitions",
    "measurement_requirements",
    "measurement_records",
    "measurement_observation_history",
    "measurement_status_history",
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
        count = (
            await conn.execute(text("SELECT count(*) FROM measurement_definitions"))
        ).scalar()
        print("definition_seed_count", count)


asyncio.run(main())
