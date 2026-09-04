"""Phase 4 migration 0005 round-trip evidence."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from brewing_api.platform.database import engine

pytestmark = pytest.mark.integration

PHASE4_PREDECESSOR = "0004_phase4_fermentation_conditioning_yeast"
EXPECTED_REVISION = "0008_phase4_yeast_provenance"
PHASE4_PREDECESSOR = "0006_phase4_lifecycle_completion"
PHASE4_SLICE2_TABLES = (
    "fermentation_measurements",
    "fermentation_measurement_corrections",
    "fermentation_derived_gravity_snapshots",
)
PHASE4_SLICE3_TABLES = ("fermentation_completion_assessments",)
PHASE4_SLICE4_TABLES = (
    "fermentation_timers",
    "fermentation_timer_revisions",
    "fermentation_reminders",
    "fermentation_reminder_history",
)
PHASE4_SLICE6_TABLES = ("fermentation_yeast_reference_history",)
DISPOSABLE_DB = "phase4_slice4_mig_validation"


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


def test_alembic_version_is_phase4_slice2_head():
    _require_postgres()
    with engine.connect() as connection:
        version = connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert version == EXPECTED_REVISION


def test_phase4_slice2_tables_exist():
    _require_postgres()
    tables = set(inspect(engine).get_table_names())
    missing = [name for name in PHASE4_SLICE2_TABLES if name not in tables]
    assert missing == []


def test_phase4_slice3_tables_exist():
    _require_postgres()
    tables = set(inspect(engine).get_table_names())
    missing = [name for name in PHASE4_SLICE3_TABLES if name not in tables]
    assert missing == []


def test_phase4_slice4_tables_exist():
    _require_postgres()
    tables = set(inspect(engine).get_table_names())
    missing = [name for name in PHASE4_SLICE4_TABLES if name not in tables]
    assert missing == []


def test_phase4_slice6_tables_exist():
    _require_postgres()
    tables = set(inspect(engine).get_table_names())
    missing = [name for name in PHASE4_SLICE6_TABLES if name not in tables]
    assert missing == []


def _insert_phase4_predecessor_session(
    connection, now, user_id, recipe_id, version_id, brew_id, handoff_id, ferm_id, stage_id
):
    connection.execute(
        text(
            "INSERT INTO users (id, created_at, username, password_hash, is_active) "
            "VALUES (:id, :now, :username, 'migration-hash', true)"
        ),
        {"id": user_id, "now": now, "username": f"phase4-mig-{user_id}"},
    )
    connection.execute(
        text(
            "INSERT INTO recipes (id, created_at, owner_id, name) "
            "VALUES (:id, :now, :owner, 'Phase4 Migration')"
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
        {"id": brew_id, "now": now, "user": user_id, "version": version_id},
    )
    connection.execute(
        text(
            "INSERT INTO brew_pitch_handoffs "
            "(id, created_at, brew_session_id, pitched_at, yeast_addition_note, actor_user_id) "
            "VALUES (:id, :now, :brew, :now, 'test yeast', :user)"
        ),
        {"id": handoff_id, "now": now, "brew": brew_id, "user": user_id},
    )
    connection.execute(
        text(
            "INSERT INTO fermentation_sessions "
            "(id, created_at, user_id, brew_session_id, brew_pitch_handoff_id, status, revision, started_at, "
            "plan_kind, materialization_rule_version, logical_plan_hash, plan_preview_hash, "
            "materialized_at) VALUES "
            "(:id, :now, :user, :brew, :handoff, 'ACTIVE', 1, :now, 'FERMENTATION_DEFAULT', "
            "'phase4-materialization-v1', 'hash', 'preview', :now)"
        ),
        {
            "id": ferm_id,
            "now": now,
            "user": user_id,
            "brew": brew_id,
            "handoff": handoff_id,
        },
    )
    connection.execute(
        text(
            "INSERT INTO fermentation_stage_instances "
            "(id, created_at, fermentation_session_id, canonical_stage_type, "
            "occurrence_number, status) VALUES "
            "(:id, :now, :session, 'ACTIVE_FERMENTATION', 1, 'ACTIVE')"
        ),
        {"id": stage_id, "now": now, "session": ferm_id},
    )


def test_alembic_roundtrip_preserves_phase4_session_on_disposable_database():
    _require_postgres()
    admin = _autocommit_engine()
    mig_url = _url_for(DISPOSABLE_DB)
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    recipe_id = uuid.uuid4()
    version_id = uuid.uuid4()
    brew_id = uuid.uuid4()
    handoff_id = uuid.uuid4()
    ferm_id = uuid.uuid4()
    stage_id = uuid.uuid4()
    try:
        _terminate_and_drop(admin, DISPOSABLE_DB)
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{DISPOSABLE_DB}"'))
        target = _render(mig_url)
        _run_alembic(target, "upgrade", "head")
        disposable = create_engine(target)
        with disposable.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == EXPECTED_REVISION
            tables = set(inspect(disposable).get_table_names())
            assert set(PHASE4_SLICE2_TABLES) <= tables
            assert set(PHASE4_SLICE3_TABLES) <= tables
            assert set(PHASE4_SLICE4_TABLES) <= tables
            assert set(PHASE4_SLICE6_TABLES) <= tables
        _run_alembic(target, "downgrade", PHASE4_PREDECESSOR)
        with disposable.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PHASE4_PREDECESSOR
            tables = set(inspect(disposable).get_table_names())
            assert "fermentation_timers" not in tables
            assert "fermentation_reminders" not in tables
            assert "fermentation_completion_assessments" in tables
            _insert_phase4_predecessor_session(
                connection,
                now,
                user_id,
                recipe_id,
                version_id,
                brew_id,
                handoff_id,
                ferm_id,
                stage_id,
            )
            connection.commit()
        _run_alembic(target, "upgrade", "head")
        with disposable.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == EXPECTED_REVISION
            status = connection.scalar(
                text("SELECT status FROM fermentation_sessions WHERE id = :id"),
                {"id": ferm_id},
            )
            assert status == "ACTIVE"
            stage_status = connection.scalar(
                text("SELECT status FROM fermentation_stage_instances WHERE id = :id"),
                {"id": stage_id},
            )
            assert stage_status == "ACTIVE"
    finally:
        _terminate_and_drop(admin, DISPOSABLE_DB)
