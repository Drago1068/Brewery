import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from brewing_api.platform.database import engine

pytestmark = pytest.mark.integration


def test_postgres_immutability_triggers_are_installed():
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL integration database is not configured")
    with engine.connect() as connection:
        trigger_names = set(
            connection.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname IN "
                    "('recipe_version_immutable', 'measurement_completed_immutable', "
                    "'inventory_ledger_immutable')"
                )
            ).scalars()
        )
    assert trigger_names == {
        "recipe_version_immutable",
        "measurement_completed_immutable",
        "inventory_ledger_immutable",
    }


def test_migration_head_and_immutability_are_enforced_by_postgres():
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL integration database is not configured")
    now = datetime.now(UTC)
    recipe_id = uuid.uuid4()
    version_id = uuid.uuid4()
    session_id = uuid.uuid4()
    stage_id = uuid.uuid4()
    measurement_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with engine.connect() as connection, connection.begin():
        # Canonical BICOS lineage migration head after `alembic upgrade head`.
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0015_phase4_journal_media_export"
        )
        connection.execute(
            text(
                "INSERT INTO users (id, created_at, username, password_hash, is_active) "
                "VALUES (:id, :now, :username, 'integration-test-hash', true)"
            ),
            {"id": user_id, "now": now, "username": f"integration-{user_id}"},
        )
        connection.execute(
            text(
                "INSERT INTO recipes (id, created_at, owner_id, name) "
                "VALUES (:id, :now, :owner, 'Trigger Test')"
            ),
            {"id": recipe_id, "now": now, "owner": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO recipe_versions "
                "(id, created_at, recipe_id, version_number, target_mash_temperature, "
                "mash_temperature_unit, target_mash_ph, mash_ph_tolerance, "
                "target_mash_gravity, mash_gravity_tolerance, planned_mash_duration_minutes) "
                "VALUES (:id, :now, :recipe, 1, 152, 'degF', 5.3, .05, 1.05, .003, 60)"
            ),
            {"id": version_id, "now": now, "recipe": recipe_id},
        )
        connection.execute(
            text(
                "INSERT INTO brew_sessions "
                "(id, created_at, user_id, recipe_version_id, status, "
                "target_mash_temperature, mash_temperature_unit, target_mash_ph, "
                "mash_ph_tolerance, target_mash_gravity, mash_gravity_tolerance, "
                "planned_mash_duration_minutes) VALUES "
                "(:id, :now, :user, :version, 'ACTIVE', 152, 'degF', 5.3, .05, 1.05, .003, 60)"
            ),
            {"id": session_id, "now": now, "user": user_id, "version": version_id},
        )
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="immutable"):
            connection.execute(
                text("UPDATE recipe_versions SET target_mash_ph = 5.4 WHERE id = :id"),
                {"id": version_id},
            )
        savepoint.rollback()

        connection.execute(
            text(
                "INSERT INTO brew_stages "
                "(id, created_at, brew_session_id, name, status, started_at, completed_at, "
                "target_duration_seconds, target_temperature, temperature_unit, target_ph, "
                "ph_tolerance, target_gravity, gravity_tolerance) VALUES "
                "(:id, :now, :session, 'MASH', 'COMPLETED', :now, :now, 3600, 152, "
                "'degF', 5.3, .05, 1.05, .003)"
            ),
            {"id": stage_id, "now": now, "session": session_id},
        )
        connection.execute(
            text(
                "INSERT INTO measurements "
                "(id, created_at, brew_stage_id, brew_session_id, measurement_type, value, unit, "
                "measured_at, provenance) "
                "VALUES (:id, :now, :stage, :session, 'MASH_PH', 5.3, 'pH', :now, 'BREWER')"
            ),
            {"id": measurement_id, "now": now, "stage": stage_id, "session": session_id},
        )
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="immutable"):
            connection.execute(
                text("UPDATE measurements SET value = 5.4 WHERE id = :id"),
                {"id": measurement_id},
            )
        savepoint.rollback()
        connection.rollback()
