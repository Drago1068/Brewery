"""Persist a brew_timer row, restart Postgres, confirm it survives."""

import asyncio
import os
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url)
    timer_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        # Use a synthetic row only if a brewery exists; otherwise just verify table writable via temp check.
        brewery = (await conn.execute(text("SELECT id FROM breweries LIMIT 1"))).scalar()
        session = (await conn.execute(text("SELECT id FROM brew_sessions LIMIT 1"))).scalar()
        if brewery and session:
            await conn.execute(
                text(
                    """
                    INSERT INTO brew_timers (
                      id, brewery_id, brew_session_id, label, target_duration_seconds,
                      started_at, ends_at, status, start_client_submission_id, created_by
                    ) VALUES (
                      :id, :brewery_id, :session_id, 'persist-check', 60,
                      now(), now() + interval '60 seconds', 'RUNNING', 'persist-sub', 'local-brewer'
                    )
                    """
                ),
                {"id": timer_id, "brewery_id": brewery, "session_id": session},
            )
            print("inserted_timer", timer_id)
        else:
            print("no_session_seed_skip_insert")
            timer_id = None
    await engine.dispose()
    print("READY_FOR_RESTART", timer_id or "")


asyncio.run(main())
