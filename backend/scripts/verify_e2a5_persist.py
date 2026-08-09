"""Best-effort row-level persistence check for E2A-5 entities after Postgres restart.

Creates a synthetic BrewSession graph only when a brewery already exists and
recipe_versions are available; otherwise reports what could not be verified.
"""

import asyncio
import json
import os
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url)
    marker = str(uuid.uuid4())
    async with engine.begin() as conn:
        brewery = (await conn.execute(text("SELECT id FROM breweries LIMIT 1"))).scalar()
        recipe_version = (
            await conn.execute(text("SELECT id, recipe_id FROM recipe_versions LIMIT 1"))
        ).first()
        session = (await conn.execute(text("SELECT id FROM brew_sessions LIMIT 1"))).scalar()
        print("brewery_present", bool(brewery))
        print("recipe_version_present", bool(recipe_version))
        print("session_present", bool(session))

        if session and brewery:
            # Timer row-level persistence
            timer_id = str(uuid.uuid4())
            await conn.execute(
                text(
                    """
                    INSERT INTO brew_timers (
                      id, brewery_id, brew_session_id, label, target_duration_seconds,
                      started_at, ends_at, status, start_client_submission_id, created_by
                    ) VALUES (
                      :id, :brewery_id, :session_id, 'e2a5-persist', 30,
                      now(), now() + interval '30 seconds', 'RUNNING', :sub, 'local-brewer'
                    )
                    """
                ),
                {
                    "id": timer_id,
                    "brewery_id": brewery,
                    "session_id": session,
                    "sub": f"persist-{marker}",
                },
            )
            print("inserted_timer", timer_id)

            plan = (
                await conn.execute(
                    text("SELECT brew_plan_id FROM brew_sessions WHERE id=:id"),
                    {"id": session},
                )
            ).scalar()
            rv = (
                await conn.execute(
                    text("SELECT recipe_version_id FROM brew_plans WHERE id=:id"),
                    {"id": plan},
                )
            ).scalar()
            handoff_id = str(uuid.uuid4())
            payload = {
                "marker": marker,
                "boundary": {"claims_fermentation_readiness": False},
                "note": "e2a5 persistence probe",
            }
            await conn.execute(
                text(
                    """
                    INSERT INTO fermentation_handoffs (
                      id, brewery_id, brew_session_id, brew_plan_id, recipe_version_id,
                      client_submission_id, created_by, brew_day_closed_at, payload
                    ) VALUES (
                      :id, :brewery_id, :session_id, :plan_id, :rv_id,
                      :sub, 'local-brewer', now(), CAST(:payload AS jsonb)
                    )
                    ON CONFLICT (brew_session_id) DO NOTHING
                    """
                ),
                {
                    "id": handoff_id,
                    "brewery_id": brewery,
                    "session_id": session,
                    "plan_id": plan,
                    "rv_id": rv,
                    "sub": f"handoff-{marker}",
                    "payload": json.dumps(payload),
                },
            )
            print("inserted_or_existing_handoff_probe", handoff_id)
            print("READY_FOR_RESTART", marker, timer_id)
        else:
            print("SKIP_ROW_INSERT_NO_SESSION")
            print("READY_FOR_RESTART", marker, "")
    await engine.dispose()


asyncio.run(main())
