"""Isolated pg_dump/pg_restore + media-byte consistency proof."""

from __future__ import annotations

import os
import subprocess
import tarfile
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from brewing_api.platform.database import engine

pytestmark = pytest.mark.integration

SOURCE_DB = "phase3_backup_source"
RESTORE_DB = "phase3_backup_restore"


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


def test_pg_dump_restore_preserves_attachment_metadata_and_media_bytes():
    _require_postgres()
    admin = _autocommit_engine()
    media_root = Path(os.environ.get("MEDIA_ROOT", "/var/lib/brewing/media"))
    media_root.mkdir(parents=True, exist_ok=True)
    storage_key = f"backup-proof/{uuid.uuid4().hex}.bin"
    media_path = media_root / storage_key
    media_path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"phase3-media-backup-bytes"
    media_path.write_bytes(payload)

    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    recipe_id = uuid.uuid4()
    version_id = uuid.uuid4()
    session_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    dump_path = Path(tempfile.gettempdir()) / f"{SOURCE_DB}.dump"
    media_tar = Path(tempfile.gettempdir()) / f"{SOURCE_DB}-media.tar"

    try:
        for name in (SOURCE_DB, RESTORE_DB):
            _terminate_and_drop(admin, name)
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{SOURCE_DB}"'))
        source_url = _render(_url_for(SOURCE_DB))
        _alembic_upgrade(source_url)
        source = create_engine(source_url)
        with source.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, created_at, username, password_hash, is_active) "
                    "VALUES (:id, :now, :username, 'hash', true)"
                ),
                {"id": user_id, "now": now, "username": f"bak-{user_id.hex[:8]}"},
            )
            connection.execute(
                text(
                    "INSERT INTO recipes (id, created_at, owner_id, name) "
                    "VALUES (:id, :now, :owner, 'Backup Ale')"
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
                    "planned_mash_duration_minutes, revision) VALUES "
                    "(:id, :now, :user, :version, 'ACTIVE', 152, 'degF', "
                    "5.3, .05, 1.05, .003, 60, 1)"
                ),
                {
                    "id": session_id,
                    "now": now,
                    "user": user_id,
                    "version": version_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO brew_attachments "
                    "(id, created_at, brew_session_id, content_type, byte_length, "
                    "sha256, storage_key, original_filename, status, actor_user_id) VALUES "
                    "(:id, :now, :session, 'application/octet-stream', :n, :checksum, "
                    ":key, 'proof.bin', 'ACTIVE', :actor)"
                ),
                {
                    "id": attachment_id,
                    "now": now,
                    "session": session_id,
                    "n": len(payload),
                    "checksum": "0" * 64,
                    "key": storage_key,
                    "actor": user_id,
                },
            )
        source.dispose()

        url = make_url(source_url)
        env = {
            **os.environ,
            "PGPASSWORD": url.password or "",
        }
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
            archive.add(media_path, arcname=storage_key)

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

        restore_media = Path(tempfile.gettempdir()) / "phase3-restore-media"
        if restore_media.exists():
            for child in restore_media.rglob("*"):
                if child.is_file():
                    child.unlink()
        restore_media.mkdir(parents=True, exist_ok=True)
        with tarfile.open(media_tar, "r") as archive:
            archive.extractall(restore_media)

        restored = create_engine(_render(_url_for(RESTORE_DB)))
        with restored.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT storage_key, byte_length FROM brew_attachments WHERE id = :id"
                ),
                {"id": attachment_id},
            ).mappings().one()
            assert row["storage_key"] == storage_key
            assert int(row["byte_length"]) == len(payload)
        restored_file = restore_media / storage_key
        assert restored_file.exists()
        assert restored_file.read_bytes() == payload
        restored.dispose()
    finally:
        if media_path.exists():
            media_path.unlink()
        for path in (dump_path, media_tar):
            if path.exists():
                path.unlink()
        for name in (RESTORE_DB, SOURCE_DB):
            try:
                _terminate_and_drop(admin, name)
            except Exception:
                pass
        admin.dispose()
