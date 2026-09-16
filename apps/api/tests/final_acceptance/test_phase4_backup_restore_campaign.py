"""Phase 4 §35 backup/restore final-acceptance campaign (verification-only).

Isolated pg_dump -Fc / pg_restore --no-owner against disposable databases.
Does not touch production NAS or the shared compose development volume.
"""

from __future__ import annotations

import hashlib
import io
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
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

from brewing_api.application.auth import password_hash
from brewing_api.domain.identity.models import User
from brewing_api.main import app
from brewing_api.platform.database import engine, get_db
from brewing_api.platform.time import utc_now

pytestmark = pytest.mark.integration

SOURCE_DB = "phase4_fa_backup_source"
RESTORE_DB = "phase4_fa_backup_restore"
MIGRATION_HEAD = "0015_phase4_journal_media_export"
REPO_ROOT = Path(__file__).resolve().parents[4]
BACKUP_SCRIPT = REPO_ROOT / "infrastructure" / "docker" / "backup-postgres.ps1"
RESTORE_SCRIPT = REPO_ROOT / "infrastructure" / "docker" / "restore-postgres.ps1"

COUNT_TABLES = (
    ("fermentation_sessions", "id"),
    ("fermentation_stage_instances", "fermentation_session_id"),
    ("fermentation_measurements", "fermentation_session_id"),
    ("fermentation_timers", "fermentation_session_id"),
    ("fermentation_reminders", "fermentation_session_id"),
    ("fermentation_journal_events", "fermentation_session_id"),
    ("fermentation_attachments", "fermentation_session_id"),
    ("fermentation_notes", "fermentation_session_id"),
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
    ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color=(40, 90, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _counts(connection, session_id: uuid.UUID) -> dict[str, int]:
    out: dict[str, int] = {}
    for table, column in COUNT_TABLES:
        if table == "fermentation_sessions":
            value = connection.execute(
                text("SELECT count(*) FROM fermentation_sessions WHERE id = :id"),
                {"id": session_id},
            ).scalar()
        else:
            value = connection.execute(
                text(f"SELECT count(*) FROM {table} WHERE {column} = :id"),
                {"id": session_id},
            ).scalar()
        out[table] = int(value or 0)
    return out


def _seed_fermentation_fixture(client: TestClient) -> dict:
    """API-only seed mirroring E2E seedActiveFermentation (Candidate 2 behavior)."""
    created = client.post(
        "/api/v1/recipes",
        json={
            "name": f"P4-FA-Backup-{uuid.uuid4().hex[:8]}",
            "target_mash_temperature": "152.00",
            "target_mash_ph": "5.30",
            "mash_ph_tolerance": "0.05",
            "target_mash_gravity": "1.050",
            "mash_gravity_tolerance": "0.003",
            "planned_mash_duration_minutes": 1,
        },
    )
    assert created.status_code in {200, 201}, created.text
    version_id = created.json()["version_id"]

    brew = client.post(
        "/api/v1/brew-sessions",
        json={"recipe_version_id": version_id, "operation_id": str(uuid.uuid4())},
    )
    assert brew.status_code in {200, 201}, brew.text
    brew_id = brew.json()["id"]
    revision = client.get(f"/api/v1/brew-sessions/{brew_id}").json()["revision"]
    started = client.post(
        f"/api/v1/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert started.status_code == 200, started.text
    revision = client.get(f"/api/v1/brew-sessions/{brew_id}").json()["revision"]
    mash = client.post(
        f"/api/v1/brew-sessions/{brew_id}/mash/start",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert mash.status_code == 200, mash.text
    mash_id = mash.json()["id"]
    for payload in (
        {
            "measurement_type": "MASH_PH",
            "value": "5.30",
            "unit": "pH",
            "operation_id": str(uuid.uuid4()),
            "method": "METER",
            "sample_temperature_c": "65.00",
            "temperature_compensated": True,
        },
        {
            "measurement_type": "MASH_GRAVITY",
            "value": "1.048",
            "unit": "SG",
            "operation_id": str(uuid.uuid4()),
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
        },
    ):
        response = client.post(
            f"/api/v1/brew-sessions/stages/{mash_id}/measurements",
            json=payload,
        )
        assert response.status_code == 201, response.text

    revision = client.get(f"/api/v1/brew-sessions/{brew_id}").json()["revision"]
    pitch = client.post(
        f"/api/v1/brew-sessions/{brew_id}/pitch-handoff",
        json={
            "operation_id": str(uuid.uuid4()),
            "yeast_addition_note": "US-05 dry yeast pitched",
            "pitch_temperature_c": "18.0",
            "expected_revision": revision,
        },
    )
    assert pitch.status_code == 201, pitch.text
    revision = client.get(f"/api/v1/brew-sessions/{brew_id}").json()["revision"]
    completed = client.post(
        f"/api/v1/brew-sessions/stages/{mash_id}/complete",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert completed.status_code == 200, completed.text

    ferm = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert ferm.status_code == 201, ferm.text
    body = ferm.json()
    active = next(s for s in body["stages"] if s["canonical_stage_type"] == "ACTIVE_FERMENTATION")
    session_id = body["id"]
    revision = body["revision"]
    stage_id = active["id"]

    for i in range(5):
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/measurements",
            json={
                "operation_id": str(uuid.uuid4()),
                "measurement_type": "FERMENTATION_TEMPERATURE",
                "value": f"{18 + i * 0.1:.1f}",
                "unit": "degC",
                "method": "PROBE",
                "observed_at": utc_now().isoformat(),
                "stage_instance_id": stage_id,
                "expected_revision": revision,
                "source": "OBSERVED",
            },
        )
        assert response.status_code == 201, response.text
        revision = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]

    note = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/notes",
        json={
            "operation_id": str(uuid.uuid4()),
            "body": "FA backup note",
            "expected_revision": revision,
        },
    )
    assert note.status_code == 201, note.text

    jpeg = _jpeg_bytes()
    uploaded = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/attachments",
        files={"file": ("ferment-a.jpg", jpeg, "image/jpeg")},
        data={"operation_id": str(uuid.uuid4()), "caption": "leaf a"},
    )
    assert uploaded.status_code == 201, uploaded.text
    uploaded2 = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/attachments",
        files={"file": ("ferment-b.jpg", jpeg, "image/jpeg")},
        data={"operation_id": str(uuid.uuid4()), "caption": "leaf b"},
    )
    assert uploaded2.status_code == 201, uploaded2.text

    return {
        "session_id": session_id,
        "attachment_ids": [uploaded.json()["id"], uploaded2.json()["id"]],
        "jpeg": jpeg,
        "brew_id": brew_id,
    }


def test_phase4_isolated_backup_restore_preserves_vectors(tmp_path, monkeypatch):
    """P4-FR-080 / P4-AC-040 / P4-ADV-030 — isolated restore equality + replay."""
    _require_postgres()
    assert BACKUP_SCRIPT.is_file()
    assert RESTORE_SCRIPT.is_file()

    from brewing_api.platform import config

    media_root = tmp_path / "source-media"
    media_root.mkdir()
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    config.get_settings.cache_clear()

    admin = _autocommit_engine()
    dump_path = Path(tempfile.gettempdir()) / f"{SOURCE_DB}.dump"
    media_tar = Path(tempfile.gettempdir()) / f"{SOURCE_DB}-media.tar"
    restore_media = tmp_path / "restore-media"
    password = "p4-backup-password-not-a-secret"
    username = f"p4bak-{uuid.uuid4().hex[:8]}"

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
            db.add(User(username=username, password_hash=password_hash.hash(password)))
            db.commit()

        def _override_source():
            db = factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_source
        try:
            with TestClient(app) as client:
                client.headers["Origin"] = "http://testserver"
                login = client.post(
                    "/api/v1/auth/login",
                    json={"username": username, "password": password},
                )
                assert login.status_code == 200, login.text
                client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
                seeded = _seed_fermentation_fixture(client)
                session_id = uuid.UUID(seeded["session_id"])
                pre_body = client.get(
                    f"/api/v1/fermentation-sessions/{seeded['session_id']}"
                ).json()
                pause_key = str(uuid.uuid4())
                paused = client.post(
                    f"/api/v1/fermentation-sessions/{seeded['session_id']}/commands/pause",
                    json={
                        "operation_id": pause_key,
                        "expected_revision": pre_body["revision"],
                    },
                )
                assert paused.status_code == 200, paused.text
                resumed = client.post(
                    f"/api/v1/fermentation-sessions/{seeded['session_id']}/commands/resume",
                    json={
                        "operation_id": str(uuid.uuid4()),
                        "expected_revision": paused.json()["revision"],
                    },
                )
                assert resumed.status_code == 200, resumed.text
                # Second lifecycle vector: abort → terminal CLOSED-class status for §35 dual fixture.  # noqa: E501
                aborted = client.post(
                    f"/api/v1/fermentation-sessions/{seeded['session_id']}/commands/abort",
                    json={
                        "operation_id": str(uuid.uuid4()),
                        "expected_revision": resumed.json()["revision"],
                        "reason": "FA backup CLOSED fixture abort after capture for restore proof",
                    },
                )
                assert aborted.status_code == 200, aborted.text
                final = client.get(f"/api/v1/fermentation-sessions/{seeded['session_id']}").json()
        finally:
            app.dependency_overrides.pop(get_db, None)

        with source.connect() as connection:
            source_counts = _counts(connection, session_id)
            head = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert head == MIGRATION_HEAD
            assert source_counts["fermentation_sessions"] == 1
            assert source_counts["fermentation_measurements"] >= 5
            assert source_counts["fermentation_attachments"] >= 2
            att = (
                connection.execute(
                    text(
                        "SELECT id, storage_key, sha256 FROM fermentation_attachments "
                        "WHERE fermentation_session_id = :id ORDER BY created_at"
                    ),
                    {"id": session_id},
                )
                .mappings()
                .all()
            )
            assert len(att) >= 2
            checksums = {str(row["id"]): row["sha256"] for row in att}
            for row in att:
                path = media_root / row["storage_key"]
                assert path.is_file()
                assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]

        source.dispose()

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
            pytest.skip(f"pg_dump unavailable: {dump.stderr}")

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
        restore_factory = sessionmaker(bind=restored, expire_on_commit=False)
        with restored.connect() as connection:
            restored_head = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
            assert restored_head == MIGRATION_HEAD
            restored_counts = _counts(connection, session_id)
            assert restored_counts == source_counts
            for row_id, checksum in checksums.items():
                row = (
                    connection.execute(
                        text(
                            "SELECT storage_key, sha256 FROM fermentation_attachments WHERE id = :id"  # noqa: E501
                        ),
                        {"id": row_id},
                    )
                    .mappings()
                    .one()
                )
                assert row["sha256"] == checksum
                assert (
                    hashlib.sha256((restore_media / row["storage_key"]).read_bytes()).hexdigest()
                    == checksum
                )

        monkeypatch.setenv("MEDIA_ROOT", str(restore_media))
        config.get_settings.cache_clear()

        def _override_restore():
            db = restore_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_restore
        try:
            with TestClient(app) as client:
                client.headers["Origin"] = "http://testserver"
                login = client.post(
                    "/api/v1/auth/login",
                    json={"username": username, "password": password},
                )
                assert login.status_code == 200, login.text
                client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
                after = client.get(f"/api/v1/fermentation-sessions/{session_id}")
                assert after.status_code == 200, after.text
                assert after.json()["id"] == str(session_id)
                assert after.json()["status"] == final["status"]
                assert after.json()["revision"] == final["revision"]
                for attachment_id in seeded["attachment_ids"]:
                    fetched = client.get(
                        f"/api/v1/fermentation-sessions/{session_id}/attachments/{attachment_id}"
                    )
                    assert fetched.status_code == 200
                    assert hashlib.sha256(fetched.content).hexdigest() == checksums[attachment_id]
                # P4-ADV-030: replay pause key — must not create a second authoritative pause.
                replay = client.post(
                    f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
                    json={
                        "operation_id": pause_key,
                        "expected_revision": after.json()["revision"],
                    },
                )
                assert replay.status_code in {200, 409}, replay.text
                if replay.status_code == 200:
                    assert replay.json()["revision"] == after.json()["revision"]
                    assert replay.json()["status"] == after.json()["status"]
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
