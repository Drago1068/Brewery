"""Phase 3 schema and Alembic round-trip evidence.

Schema-presence tests use the shared integration database.
Round-trip A–G runs on a disposable PostgreSQL database so the live
application database is never downgraded.
"""

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from phase3_migration_regression import assert_phase3_migration_ancestry
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import DBAPIError

from brewing_api.platform.database import engine

pytestmark = pytest.mark.integration

EXPECTED_REVISION = "0003_phase3_brew_day_os"
PHASE2_REVISION = "0002_phase2_brewing_core"
PHASE3_TABLES = (
    "brew_plan_steps",
    "brew_operations",
    "brew_addition_events",
    "brew_waivers",
    "brew_attachments",
)
DISPOSABLE_DB = "phase3_mig_validation"


def _version(connection) -> str | None:
    return connection.scalar(text("SELECT version_num FROM alembic_version"))


def _require_postgres() -> None:
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL integration database is not configured")


def _alembic(url: str) -> Config:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _run_alembic(url: str, action: str, revision: str) -> None:
    os.environ["ALEMBIC_DATABASE_URL"] = url
    cfg = _alembic(url)
    if action == "upgrade":
        command.upgrade(cfg, revision)
    else:
        command.downgrade(cfg, revision)


def _url_for(database: str):
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        pytest.skip("DATABASE_URL is not set")
    return make_url(raw).set(database=database)


def _render(url) -> str:
    return url.render_as_string(hide_password=False)


def _autocommit_engine(database: str = "postgres") -> Engine:
    return create_engine(_render(_url_for(database)), isolation_level="AUTOCOMMIT")


def _terminate_and_drop(admin: Engine, database: str) -> None:
    with admin.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": database},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{database}"'))


def test_alembic_version_is_phase3_head():
    """Accepted Phase 3 head remains an ancestor of the live PostgreSQL migration head."""
    _require_postgres()
    with engine.connect() as connection:
        version = connection.scalar(text("SELECT version_num FROM alembic_version"))
    root = Path(__file__).resolve().parents[3]
    assert assert_phase3_migration_ancestry(root, head_revision=version) == version


def test_phase3_tables_exist():
    _require_postgres()
    tables = set(inspect(engine).get_table_names())
    missing = [name for name in PHASE3_TABLES if name not in tables]
    assert missing == []


def test_brew_plan_steps_immutability_trigger():
    _require_postgres()
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    recipe_id = uuid.uuid4()
    version_id = uuid.uuid4()
    session_id = uuid.uuid4()
    step_id = uuid.uuid4()
    plan_step_id = uuid.uuid4()
    with engine.connect() as connection, connection.begin():
        trigger_names = set(
            connection.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname IN "
                    "('brew_plan_steps_immutable', 'brew_requirement_templates_immutable')"
                )
            ).scalars()
        )
        assert trigger_names == {
            "brew_plan_steps_immutable",
            "brew_requirement_templates_immutable",
        }
        connection.execute(
            text(
                "INSERT INTO users (id, created_at, username, password_hash, is_active) "
                "VALUES (:id, :now, :username, 'integration-test-hash', true)"
            ),
            {"id": user_id, "now": now, "username": f"phase3-mig-{user_id}"},
        )
        connection.execute(
            text(
                "INSERT INTO recipes (id, created_at, owner_id, name) "
                "VALUES (:id, :now, :owner, 'Phase3 Migration')"
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
                "(:id, :now, :user, :version, 'PLANNED', 152, 'degF', 5.3, .05, 1.05, .003, 60)"
            ),
            {"id": session_id, "now": now, "user": user_id, "version": version_id},
        )
        connection.execute(
            text(
                "INSERT INTO brew_plan_steps "
                "(id, created_at, brew_session_id, plan_step_id, canonical_stage_type, "
                "required, source_kind, stable_source_discriminator, expansion_rank, "
                "planned_same_type_ordinal, source_sequence, clock_basis, sort_index, payload) "
                "VALUES (:id, :now, :session, :plan, 'MASH', true, 'LEGACY', 'legacy-mash', "
                "0, 1, 1, 'WALL_CLOCK', 0, '{}'::json)"
            ),
            {"id": step_id, "now": now, "session": session_id, "plan": plan_step_id},
        )
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="immutable"):
            connection.execute(
                text("UPDATE brew_plan_steps SET required = false WHERE id = :id"),
                {"id": step_id},
            )
        savepoint.rollback()
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="immutable"):
            connection.execute(
                text("DELETE FROM brew_plan_steps WHERE id = :id"),
                {"id": step_id},
            )
        savepoint.rollback()
        connection.rollback()


def _insert_phase2_session(connection, now, user_id, recipe_id, version_id, session_id, stage_id):
    connection.execute(
        text(
            "INSERT INTO users (id, created_at, username, password_hash, is_active) "
            "VALUES (:id, :now, :username, 'migration-hash', true)"
        ),
        {"id": user_id, "now": now, "username": f"phase3-roundtrip-{user_id}"},
    )
    connection.execute(
        text(
            "INSERT INTO recipes (id, created_at, owner_id, name) "
            "VALUES (:id, :now, :owner, 'Roundtrip Ale')"
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
            "(:id, :now, :user, :version, 'COMPLETED', 152, 'degF', 5.3, .05, 1.05, .003, 60)"
        ),
        {"id": session_id, "now": now, "user": user_id, "version": version_id},
    )
    connection.execute(
        text(
            "INSERT INTO brew_stages "
            "(id, created_at, brew_session_id, name, status, target_duration_seconds, "
            "target_temperature, temperature_unit, target_ph, ph_tolerance, "
            "target_gravity, gravity_tolerance) VALUES "
            "(:id, :now, :session, 'Mash', 'COMPLETED', 3600, 152, 'degF', 5.3, .05, 1.05, .003)"
        ),
        {"id": stage_id, "now": now, "session": session_id},
    )


def test_alembic_roundtrip_preserves_phase2_session_on_disposable_database():
    _require_postgres()
    admin = _autocommit_engine()
    mig_url = _url_for(DISPOSABLE_DB)
    restore_db = "phase3_restore_validation"
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    recipe_id = uuid.uuid4()
    version_id = uuid.uuid4()
    session_id = uuid.uuid4()
    stage_id = uuid.uuid4()
    try:
        _terminate_and_drop(admin, DISPOSABLE_DB)
        _terminate_and_drop(admin, restore_db)
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{DISPOSABLE_DB}"'))
        target = _render(mig_url)
        _run_alembic(target, "upgrade", EXPECTED_REVISION)
        disposable = create_engine(target)
        with disposable.connect() as connection:
            assert _version(connection) == EXPECTED_REVISION
            tables = set(inspect(disposable).get_table_names())
            assert set(PHASE3_TABLES) <= tables
        _run_alembic(target, "downgrade", PHASE2_REVISION)
        with disposable.connect() as connection:
            assert _version(connection) == PHASE2_REVISION
            tables = set(inspect(disposable).get_table_names())
            assert "brew_plan_steps" not in tables
            _insert_phase2_session(
                connection, now, user_id, recipe_id, version_id, session_id, stage_id
            )
            connection.commit()
        _run_alembic(target, "upgrade", EXPECTED_REVISION)
        with disposable.connect() as connection:
            assert _version(connection) == EXPECTED_REVISION
            status = connection.scalar(
                text("SELECT status FROM brew_sessions WHERE id = :id"), {"id": session_id}
            )
            stage_name = connection.scalar(
                text("SELECT name FROM brew_stages WHERE id = :id"), {"id": stage_id}
            )
            assert status == "COMPLETED"
            assert stage_name == "Mash"
            assert connection.scalar(text("SELECT COUNT(*) FROM brew_plan_steps")) == 0
        _run_alembic(target, "downgrade", PHASE2_REVISION)
        with disposable.connect() as connection:
            assert _version(connection) == PHASE2_REVISION
            assert (
                connection.scalar(
                    text("SELECT id FROM brew_sessions WHERE id = :id"),
                    {"id": session_id},
                )
                == session_id
            )
        _run_alembic(target, "upgrade", EXPECTED_REVISION)
        with disposable.connect() as connection:
            assert _version(connection) == EXPECTED_REVISION
            assert (
                connection.scalar(
                    text("SELECT status FROM brew_sessions WHERE id = :id"), {"id": session_id}
                )
                == "COMPLETED"
            )
        disposable.dispose()
        with admin.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": DISPOSABLE_DB},
            )
            conn.execute(text(f'CREATE DATABASE "{restore_db}" TEMPLATE "{DISPOSABLE_DB}"'))
        restored = create_engine(_render(_url_for(restore_db)))
        with restored.connect() as connection:
            assert _version(connection) == EXPECTED_REVISION
            assert (
                connection.scalar(
                    text("SELECT status FROM brew_sessions WHERE id = :id"), {"id": session_id}
                )
                == "COMPLETED"
            )
            tables = set(inspect(restored).get_table_names())
            assert set(PHASE3_TABLES) <= tables
        restored.dispose()
    finally:
        try:
            _terminate_and_drop(admin, restore_db)
        except Exception:
            pass
        try:
            _terminate_and_drop(admin, DISPOSABLE_DB)
        except Exception:
            pass
        admin.dispose()
