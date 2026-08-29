"""PostgreSQL invariant proofs for Phase 3 remediation on a disposable database."""

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from brewing_api.platform.database import engine

pytestmark = pytest.mark.integration

DISPOSABLE_DB = "phase3_invariant_validation"


def _require_postgres() -> None:
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL integration database is not configured")


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


def _alembic_upgrade(url: str) -> None:
    os.environ["ALEMBIC_DATABASE_URL"] = url
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="module")
def invariant_db():
    _require_postgres()
    admin = _autocommit_engine()
    target = _render(_url_for(DISPOSABLE_DB))
    try:
        _terminate_and_drop(admin, DISPOSABLE_DB)
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{DISPOSABLE_DB}"'))
        _alembic_upgrade(target)
        disposable = create_engine(target)
        yield disposable
        disposable.dispose()
    finally:
        try:
            _terminate_and_drop(admin, DISPOSABLE_DB)
        except Exception:
            pass
        admin.dispose()


def _seed_two_sessions(connection, now):
    user_id = uuid.uuid4()
    recipe_id = uuid.uuid4()
    version_id = uuid.uuid4()
    session_a = uuid.uuid4()
    session_b = uuid.uuid4()
    stage_a = uuid.uuid4()
    stage_b = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO users (id, created_at, username, password_hash, is_active) "
            "VALUES (:id, :now, :username, 'hash', true)"
        ),
        {"id": user_id, "now": now, "username": f"inv-{user_id.hex[:8]}"},
    )
    connection.execute(
        text(
            "INSERT INTO recipes (id, created_at, owner_id, name) "
            "VALUES (:id, :now, :owner, 'Inv')"
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
    for session_id, status in ((session_a, "ACTIVE"), (session_b, "COMPLETED")):
        connection.execute(
            text(
                "INSERT INTO brew_sessions "
                "(id, created_at, user_id, recipe_version_id, status, "
                "target_mash_temperature, mash_temperature_unit, target_mash_ph, "
                "mash_ph_tolerance, target_mash_gravity, mash_gravity_tolerance, "
                "planned_mash_duration_minutes, revision) VALUES "
                "(:id, :now, :user, :version, :status, 152, 'degF', 5.3, .05, 1.05, .003, 60, 1)"
            ),
            {
                "id": session_id,
                "now": now,
                "user": user_id,
                "version": version_id,
                "status": status,
            },
        )
    for stage_id, session_id in ((stage_a, session_a), (stage_b, session_b)):
        connection.execute(
            text(
                "INSERT INTO brew_stages "
                "(id, created_at, brew_session_id, name, status, "
                "target_duration_seconds, target_temperature, temperature_unit, target_ph, "
                "ph_tolerance, target_gravity, gravity_tolerance, occurrence_number, required) "
                "VALUES (:id, :now, :session, 'MASH', 'ACTIVE', 3600, 152, 'degF', 5.3, .05, "
                "1.05, .003, 1, true)"
            ),
            {"id": stage_id, "now": now, "session": session_id},
        )
    return session_a, session_b, stage_a, stage_b


def _expect_integrity_failure(connection, statement: str, params: dict) -> None:
    savepoint = connection.begin_nested()
    with pytest.raises((DBAPIError, IntegrityError)):
        connection.execute(text(statement), params)
    savepoint.rollback()


def test_append_only_triggers_exist(invariant_db):
    with invariant_db.connect() as connection:
        triggers = set(
            connection.execute(
                text(
                    "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal "
                    "AND tgname LIKE '%append_only%'"
                )
            ).scalars()
        )
    assert "brew_addition_events_append_only" in triggers
    assert "brew_addition_corrections_append_only" in triggers
    assert "measurements_append_only" in triggers


def test_cross_session_timer_reference_is_rejected(invariant_db):
    now = datetime.now(UTC)
    with invariant_db.connect() as connection, connection.begin():
        session_a, session_b, stage_a, _stage_b = _seed_two_sessions(connection, now)
        timer_id = uuid.uuid4()
        savepoint = connection.begin_nested()
        with pytest.raises((DBAPIError, IntegrityError)):
            connection.execute(
                text(
                    "INSERT INTO brew_timers "
                    "(id, created_at, brew_stage_id, brew_session_id, name, status, started_at, "
                    "planned_duration_seconds, accumulated_pause_seconds, clock_basis, revision, "
                    "timer_type, continues_after_stage) VALUES "
                    "(:id, :now, :stage, :session, 'bad', 'RUNNING', :now, 60, 0, 'WALL_CLOCK', 1, "
                    "'AUXILIARY', false)"
                ),
                {"id": timer_id, "now": now, "stage": stage_a, "session": session_b},
            )
        savepoint.rollback()
        connection.execute(
            text(
                "INSERT INTO brew_timers "
                "(id, created_at, brew_stage_id, brew_session_id, name, status, started_at, "
                "planned_duration_seconds, accumulated_pause_seconds, clock_basis, revision, "
                "timer_type, continues_after_stage) VALUES "
                "(:id, :now, :stage, :session, 'ok', 'RUNNING', :now, 60, 0, 'WALL_CLOCK', 1, "
                "'AUXILIARY', false)"
            ),
            {"id": timer_id, "now": now, "stage": stage_a, "session": session_a},
        )
        connection.rollback()


def test_cross_session_attachment_is_rejected(invariant_db):
    now = datetime.now(UTC)
    with invariant_db.connect() as connection, connection.begin():
        _session_a, session_b, stage_a, _stage_b = _seed_two_sessions(connection, now)
        _expect_integrity_failure(
            connection,
            "INSERT INTO brew_attachments "
            "(id, created_at, brew_session_id, stage_instance_id, storage_key, "
            "content_type, byte_length, sha256, status, actor_user_id) VALUES "
            "(:id, :now, :session, :stage, :key, 'image/png', 8, :sha, 'FINAL', :actor)",
            {
                "id": uuid.uuid4(),
                "now": now,
                "session": session_b,
                "stage": stage_a,
                "key": f"cross-{uuid.uuid4().hex[:12]}",
                "sha": "a" * 64,
                "actor": uuid.uuid4(),
            },
        )
        connection.rollback()


def test_cross_session_stage_requirement_is_rejected(invariant_db):
    now = datetime.now(UTC)
    with invariant_db.connect() as connection, connection.begin():
        _session_a, session_b, stage_a, _stage_b = _seed_two_sessions(connection, now)
        _expect_integrity_failure(
            connection,
            "INSERT INTO brew_stage_requirements "
            "(id, created_at, brew_session_id, stage_instance_id, requirement_template_id, "
            "requirement_class, requirement_id, status, required, waivable, provenance, "
            "payload) VALUES "
            "(:id, :now, :session, :stage, :template, 'MEASUREMENT', :req, 'PENDING', "
            "true, true, 'PLANNED', CAST(:payload AS json))",
            {
                "id": uuid.uuid4(),
                "now": now,
                "session": session_b,
                "stage": stage_a,
                "template": uuid.uuid4(),
                "req": uuid.uuid4(),
                "payload": "{}",
            },
        )
        connection.rollback()


def test_cross_session_measurement_correction_is_rejected(invariant_db):
    now = datetime.now(UTC)
    with invariant_db.connect() as connection, connection.begin():
        session_a, session_b, stage_a, stage_b = _seed_two_sessions(connection, now)
        measurement_a = uuid.uuid4()
        measurement_b = uuid.uuid4()
        for measurement_id, stage_id, session_id in (
            (measurement_a, stage_a, session_a),
            (measurement_b, stage_b, session_b),
        ):
            connection.execute(
                text(
                    "INSERT INTO measurements "
                    "(id, created_at, brew_stage_id, brew_session_id, measurement_type, "
                    "value, unit, measured_at, provenance, late_entry) VALUES "
                    "(:id, :now, :stage, :session, 'MASH_PH', 5.3, 'pH', :now, 'BREWER', false)"
                ),
                {
                    "id": measurement_id,
                    "now": now,
                    "stage": stage_id,
                    "session": session_id,
                },
            )
        _expect_integrity_failure(
            connection,
            "INSERT INTO measurements "
            "(id, created_at, brew_stage_id, brew_session_id, measurement_type, "
            "value, unit, measured_at, provenance, late_entry, correction_of_id) VALUES "
            "(:id, :now, :stage, :session, 'MASH_PH', 5.4, 'pH', :now, 'BREWER', false, "
            ":original)",
            {
                "id": uuid.uuid4(),
                "now": now,
                "stage": stage_a,
                "session": session_a,
                "original": measurement_b,
            },
        )
        connection.rollback()


def test_cross_session_addition_correction_original_is_rejected(invariant_db):
    now = datetime.now(UTC)
    with invariant_db.connect() as connection, connection.begin():
        session_a, session_b, stage_a, stage_b = _seed_two_sessions(connection, now)
        event_a = uuid.uuid4()
        event_b = uuid.uuid4()
        for event_id, stage_id, session_id in (
            (event_a, stage_a, session_a),
            (event_b, stage_b, session_b),
        ):
            connection.execute(
                text(
                    "INSERT INTO brew_addition_events "
                    "(id, created_at, brew_session_id, stage_instance_id, requirement_id, "
                    "execution_status, late_entry) VALUES "
                    "(:id, :now, :session, :stage, :req, 'EXECUTED', false)"
                ),
                {
                    "id": event_id,
                    "now": now,
                    "session": session_id,
                    "stage": stage_id,
                    "req": uuid.uuid4(),
                },
            )
        _expect_integrity_failure(
            connection,
            "INSERT INTO brew_addition_corrections "
            "(id, created_at, brew_session_id, stage_instance_id, "
            "original_addition_event_id, correction_of_id, execution_status, "
            "changed_fields, reason, actor_user_id, recorded_at, late_entry) VALUES "
            "(:id, :now, :session, :stage, :original, :correction_of, 'EXECUTED', "
            "CAST(:changed AS json), 'cross-session original lineage must be rejected', "
            ":actor, :now, false)",
            {
                "id": uuid.uuid4(),
                "now": now,
                "session": session_b,
                "stage": stage_b,
                "original": event_a,
                "correction_of": event_b,
                "changed": "{}",
                "actor": uuid.uuid4(),
            },
        )
        connection.rollback()


def test_addition_event_update_and_delete_are_rejected(invariant_db):
    now = datetime.now(UTC)
    with invariant_db.connect() as connection, connection.begin():
        session_a, _session_b, stage_a, _stage_b = _seed_two_sessions(connection, now)
        event_id = uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO brew_addition_events "
                "(id, created_at, brew_session_id, stage_instance_id, requirement_id, "
                "execution_status, late_entry) VALUES "
                "(:id, :now, :session, :stage, :req, 'EXECUTED', false)"
            ),
            {
                "id": event_id,
                "now": now,
                "session": session_a,
                "stage": stage_a,
                "req": uuid.uuid4(),
            },
        )
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="immutable"):
            connection.execute(
                text("UPDATE brew_addition_events SET actual_quantity = 1 WHERE id = :id"),
                {"id": event_id},
            )
        savepoint.rollback()
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="immutable"):
            connection.execute(
                text("DELETE FROM brew_addition_events WHERE id = :id"), {"id": event_id}
            )
        savepoint.rollback()
        connection.rollback()


def test_addition_correction_requires_existing_event_fk(invariant_db):
    now = datetime.now(UTC)
    with invariant_db.connect() as connection, connection.begin():
        session_a, _session_b, stage_a, _stage_b = _seed_two_sessions(connection, now)
        event_id = uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO brew_addition_events "
                "(id, created_at, brew_session_id, stage_instance_id, requirement_id, "
                "execution_status, late_entry) VALUES "
                "(:id, :now, :session, :stage, :req, 'EXECUTED', false)"
            ),
            {
                "id": event_id,
                "now": now,
                "session": session_a,
                "stage": stage_a,
                "req": uuid.uuid4(),
            },
        )
        savepoint = connection.begin_nested()
        with pytest.raises((DBAPIError, IntegrityError)):
            connection.execute(
                text(
                    "INSERT INTO brew_addition_corrections "
                    "(id, created_at, brew_session_id, stage_instance_id, "
                    "original_addition_event_id, correction_of_id, execution_status, "
                    "changed_fields, reason, actor_user_id, recorded_at, late_entry) VALUES "
                    "(:id, :now, :session, :stage, :original, :missing, 'EXECUTED', "
                    "CAST(:changed AS json), 'bad fk reference for remediation proof', "
                    ":actor, :now, false)"
                ),
                {
                    "id": uuid.uuid4(),
                    "now": now,
                    "session": session_a,
                    "stage": stage_a,
                    "original": event_id,
                    "missing": uuid.uuid4(),
                    "changed": "{}",
                    "actor": uuid.uuid4(),
                },
            )
        savepoint.rollback()
        connection.rollback()
