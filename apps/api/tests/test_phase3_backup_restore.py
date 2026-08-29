"""Isolated pg_dump/pg_restore + media-byte consistency proof.

Operational scripts `infrastructure/docker/backup-postgres.ps1` and
`restore-postgres.ps1` wrap `pg_dump -Fc`, `pg_restore --no-owner`, and a tar of
MEDIA_ROOT via `docker compose exec` against the development database. Restore
requires interactive confirmation (`RESTORE`) and replaces the live volume.

This test therefore does not invoke those scripts by default: they would mutate
the shared development database. It executes the same dump/restore/media-copy
commands against isolated PostgreSQL databases, which is the runnable equivalent
in pytest. Set PHASE3_INVOKE_BACKUP_SCRIPTS=1 only in a dedicated disposable
compose project.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker
from test_phase3_engines import PNG

from brewing_api.application.auth import password_hash
from brewing_api.application.phase3.performance import (
    create_isolated_benchmark_session,
    describe_benchmark_dataset,
)
from brewing_api.domain.brew_day.models import BrewAttachment
from brewing_api.domain.identity.models import User
from brewing_api.main import app
from brewing_api.platform.database import engine, get_db

pytestmark = pytest.mark.integration

SOURCE_DB = "phase3_backup_source"
RESTORE_DB = "phase3_backup_restore"
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKUP_SCRIPT = REPO_ROOT / "infrastructure" / "docker" / "backup-postgres.ps1"
RESTORE_SCRIPT = REPO_ROOT / "infrastructure" / "docker" / "restore-postgres.ps1"
MIGRATION_HEAD = "0003_phase3_brew_day_os"
COUNT_TABLES = (
    "brew_sessions",
    "brew_stages",
    "brew_timers",
    "notifications",
    "measurements",
    "brew_addition_events",
    "brew_addition_corrections",
    "brew_notes",
    "brew_attachments",
    "brew_journal_events",
)


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


def _counts(connection, session_id: uuid.UUID) -> dict[str, int]:
    counts = {}
    for table in COUNT_TABLES:
        column = "id" if table == "brew_sessions" else "brew_session_id"
        if table == "brew_sessions":
            value = connection.execute(
                text("SELECT count(*) FROM brew_sessions WHERE id = :id"),
                {"id": session_id},
            ).scalar()
        else:
            value = connection.execute(
                text(f"SELECT count(*) FROM {table} WHERE {column} = :id"),
                {"id": session_id},
            ).scalar()
        counts[table] = int(value or 0)
    return counts


def _operational_scripts_runnable() -> tuple[bool, str]:
    if not BACKUP_SCRIPT.is_file() or not RESTORE_SCRIPT.is_file():
        return False, "operational backup/restore scripts are missing"
    if os.environ.get("PHASE3_INVOKE_BACKUP_SCRIPTS") != "1":
        return (
            False,
            "backup-postgres.ps1/restore-postgres.ps1 target the compose development "
            "database and restore-postgres.ps1 prompts for RESTORE; pytest uses an "
            "isolated pg_dump -Fc / pg_restore --no-owner + media tar path that "
            "mirrors those scripts without mutating the live volume",
        )
    return True, "PHASE3_INVOKE_BACKUP_SCRIPTS=1"


def test_pg_dump_restore_preserves_attachment_metadata_and_media_bytes(tmp_path, monkeypatch):
    _require_postgres()
    assert BACKUP_SCRIPT.is_file()
    assert RESTORE_SCRIPT.is_file()
    runnable, script_reason = _operational_scripts_runnable()
    # Default CI path mirrors backup-postgres.ps1 / restore-postgres.ps1 with
    # isolated pg_dump -Fc + media tar + pg_restore --no-owner so the live
    # compose volume is never mutated. Dedicated disposable hosts may set
    # PHASE3_INVOKE_BACKUP_SCRIPTS=1 to exercise the PowerShell scripts directly.
    if runnable:
        assert "PHASE3_INVOKE_BACKUP_SCRIPTS=1" in script_reason
    else:
        assert "isolated" in script_reason or "missing" in script_reason

    from brewing_api.platform import config

    media_root = tmp_path / "source-media"
    media_root.mkdir()
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    config.get_settings.cache_clear()

    admin = _autocommit_engine()
    dump_path = Path(tempfile.gettempdir()) / f"{SOURCE_DB}.dump"
    media_tar = Path(tempfile.gettempdir()) / f"{SOURCE_DB}-media.tar"
    restore_media = tmp_path / "restore-media"
    password = "backup-password-not-a-secret"
    username = f"bak-{uuid.uuid4().hex[:8]}"

    try:
        for name in (SOURCE_DB, RESTORE_DB):
            _terminate_and_drop(admin, name)
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{SOURCE_DB}"'))
        source_url = _render(_url_for(SOURCE_DB))
        _alembic_upgrade(source_url)
        source = create_engine(source_url)
        factory = sessionmaker(bind=source, expire_on_commit=False)
        with factory() as db:
            user = User(username=username, password_hash=password_hash.hash(password))
            db.add(user)
            db.commit()
            session = create_isolated_benchmark_session(db, user)
            session_id = session.id
            attachment = db.scalar(
                select(BrewAttachment).where(BrewAttachment.brew_session_id == session_id)
            )
            assert attachment is not None
            payload_path = media_root / attachment.storage_key
            payload_path.write_bytes(PNG)
            attachment.content_type = "image/png"
            attachment.byte_length = len(PNG)
            attachment.sha256 = hashlib.sha256(PNG).hexdigest()
            attachment.original_filename = "mash.png"
            db.commit()
            attachment_id = attachment.id
            checksum = attachment.sha256
            storage_key = attachment.storage_key
            dataset = describe_benchmark_dataset(db, session_id)
        with source.connect() as connection:
            source_counts = _counts(connection, session_id)
            head = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert head == MIGRATION_HEAD
        source.dispose()

        assert dataset["canonical_stage_count"] >= 13
        assert dataset["repeated_occurrences"] >= 3
        assert source_counts["brew_timers"] >= 10
        assert source_counts["notifications"] >= 20
        assert source_counts["measurements"] >= 100
        assert source_counts["brew_addition_events"] >= 1
        assert source_counts["brew_addition_corrections"] >= 1
        assert source_counts["brew_notes"] >= 1
        assert source_counts["brew_attachments"] >= 1
        assert source_counts["brew_journal_events"] >= 1
        assert (media_root / storage_key).is_file()
        assert hashlib.sha256((media_root / storage_key).read_bytes()).hexdigest() == checksum

        url = make_url(source_url)
        env = {**os.environ, "PGPASSWORD": url.password or ""}
        try:
            dump = subprocess.run(
                [
                    "pg_dump",
                    "-h",
                    url.host or "db",
                    "-p",
                    str(url.port or 5432),
                    "-U",
                    url.username or "brewing_app",
                    "-d",
                    SOURCE_DB,
                    "-Fc",
                    "-f",
                    str(dump_path),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            pytest.skip("pg_dump binary is not available in this runtime")
        if dump.returncode != 0:
            pytest.skip(f"pg_dump unavailable in this runtime: {dump.stderr}")

        with tarfile.open(media_tar, "w") as archive:
            for child in media_root.iterdir():
                archive.add(child, arcname=child.name)

        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{RESTORE_DB}"'))
        restore = subprocess.run(
            [
                "pg_restore",
                "-h",
                url.host or "db",
                "-p",
                str(url.port or 5432),
                "-U",
                url.username or "brewing_app",
                "-d",
                RESTORE_DB,
                "--no-owner",
                str(dump_path),
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if restore.returncode != 0:
            pytest.fail(f"pg_restore failed: {restore.stderr}")

        restore_media.mkdir(parents=True, exist_ok=True)
        with tarfile.open(media_tar, "r") as archive:
            archive.extractall(restore_media, filter="data")

        restore_url = _render(_url_for(RESTORE_DB))
        restored = create_engine(restore_url)
        with restored.connect() as connection:
            restored_head = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
            assert restored_head == MIGRATION_HEAD
            restored_counts = _counts(connection, session_id)
            assert restored_counts == source_counts
            row = (
                connection.execute(
                    text(
                        "SELECT storage_key, byte_length, sha256 FROM brew_attachments "
                        "WHERE id = :id"
                    ),
                    {"id": attachment_id},
                )
                .mappings()
                .one()
            )
            assert row["storage_key"] == storage_key
            assert row["sha256"] == checksum
        restored_file = restore_media / storage_key
        assert restored_file.exists()
        body = restored_file.read_bytes()
        assert hashlib.sha256(body).hexdigest() == checksum
        assert body == PNG

        monkeypatch.setenv("MEDIA_ROOT", str(restore_media))
        config.get_settings.cache_clear()

        def _override_db():
            SessionRestore = sessionmaker(bind=restored, expire_on_commit=False)
            db = SessionRestore()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_db
        try:
            with TestClient(app) as client:
                client.headers["Origin"] = "http://testserver"
                login = client.post(
                    "/api/v1/auth/login",
                    json={"username": username, "password": password},
                )
                assert login.status_code == 200, login.text
                fetched = client.get(
                    f"/api/v1/brew-sessions/{session_id}/attachments/{attachment_id}"
                )
                assert fetched.status_code == 200
                assert fetched.content == PNG
                assert hashlib.sha256(fetched.content).hexdigest() == checksum
        finally:
            app.dependency_overrides.pop(get_db, None)
        restored.dispose()
    finally:
        config.get_settings.cache_clear()
        for path in (dump_path, media_tar):
            if path.exists():
                path.unlink()
        for name in (RESTORE_DB, SOURCE_DB):
            try:
                _terminate_and_drop(admin, name)
            except Exception:
                pass
        admin.dispose()
