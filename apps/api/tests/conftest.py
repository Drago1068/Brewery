import os
import uuid

if os.environ.get("TEST_USE_POSTGRES") != "1":
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./.test-brewing.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["BOOTSTRAP_ADMIN_USERNAME"] = "brewer"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "test-password-not-a-secret"
os.environ["SESSION_SECRET"] = "test-session-secret-with-at-least-32-characters"
os.environ["PUBLIC_ORIGIN"] = "http://testserver"
os.environ["CORS_ORIGINS"] = "http://testserver"
os.environ.setdefault("MEDIA_ROOT", os.path.join(os.path.dirname(__file__), ".test-media"))

import pytest
from fastapi.testclient import TestClient

pytest_plugins = ["phase4_fixtures"]

from brewing_api.application.phase3.csrf import reset_rate_limits
from brewing_api.domain import model_registry  # noqa: F401
from brewing_api.main import app
from brewing_api.platform.database import Base, engine


def _truncate_postgres() -> None:
    """Full isolation for PostgreSQL: truncate all app tables, keep alembic_version."""
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                DO $$
                DECLARE
                  r RECORD;
                BEGIN
                  FOR r IN (
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                      AND tablename <> 'alembic_version'
                  ) LOOP
                    EXECUTE 'TRUNCATE TABLE '
                      || quote_ident(r.tablename)
                      || ' RESTART IDENTITY CASCADE';
                  END LOOP;
                END $$;
                """
            )
        )


@pytest.fixture(autouse=True)
def clean_database():
    reset_rate_limits()
    if os.environ.get("TEST_USE_POSTGRES") == "1":
        _truncate_postgres()
        yield
        reset_rate_limits()
        return
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        Base.metadata.drop_all(bind=connection)
        Base.metadata.create_all(bind=connection)
        connection.execute(text("PRAGMA foreign_keys=ON"))
    yield
    reset_rate_limits()


@pytest.fixture
def client():
    """Wire TestClient with CSRF capture only — do NOT inject operation_id/revision.

    Real clients must supply normative command identity; tests must exercise the
    actual wire contract (P3-IMPL-RR-002).
    """
    with TestClient(app) as test_client:
        test_client.headers["Origin"] = "http://testserver"
        original_post = test_client.post

        def post_with_csrf(*args, **kwargs):
            path = str(args[0]) if args else ""
            response = original_post(*args, **kwargs)
            if "/auth/login" in path and response.status_code == 200:
                token = response.json().get("csrf_token")
                if token:
                    test_client.headers["X-CSRF-Token"] = token
            return response

        test_client.post = post_with_csrf  # type: ignore[method-assign]
        yield test_client


@pytest.fixture
def authenticated_client(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "brewer", "password": "test-password-not-a-secret"},
    )
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


@pytest.fixture
def recipe_payload():
    return {
        "name": "Architecture Ale",
        "target_mash_temperature": "152.00",
        "target_mash_ph": "5.30",
        "mash_ph_tolerance": "0.05",
        "target_mash_gravity": "1.050",
        "mash_gravity_tolerance": "0.003",
        "planned_mash_duration_minutes": 1,
    }


def _command(client: TestClient, session_id: str | None = None, **extra) -> dict:
    """Build a normative SessionCommand body for the current session revision."""
    body: dict = {"operation_id": str(uuid.uuid4()), **extra}
    if "expected_revision" not in body:
        if session_id:
            got = client.get(f"/api/v1/brew-sessions/{session_id}")
        else:
            got = client.get("/api/v1/brew-sessions/active")
        if got.status_code == 200 and got.json() and got.json().get("revision") is not None:
            body["expected_revision"] = got.json()["revision"]
    return body


@pytest.fixture
def active_mash(authenticated_client: TestClient, recipe_payload: dict):
    existing = authenticated_client.get("/api/v1/brew-sessions/active")
    if existing.status_code == 200:
        body = existing.json()
        if body and body.get("id"):
            aborted = authenticated_client.post(
                f"/api/v1/brew-sessions/{body['id']}/abort",
                json=_command(
                    authenticated_client,
                    body["id"],
                    reason="Clearing prior test brew session before fixture",
                ),
            )
            assert aborted.status_code == 200, aborted.text

    recipe = authenticated_client.post("/api/v1/recipes", json=recipe_payload).json()
    session_response = authenticated_client.post(
        "/api/v1/brew-sessions",
        json={
            "recipe_version_id": recipe["version_id"],
            "operation_id": str(uuid.uuid4()),
        },
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]
    started = authenticated_client.post(
        f"/api/v1/brew-sessions/{session_id}/start",
        json=_command(authenticated_client, session_id),
    )
    assert started.status_code == 200, started.text
    mash_response = authenticated_client.post(
        f"/api/v1/brew-sessions/{session_id}/mash/start",
        json=_command(authenticated_client, session_id),
    )
    assert mash_response.status_code == 200, mash_response.text
    return {
        "client": authenticated_client,
        "recipe": recipe,
        "session_id": session_id,
        "stage_id": mash_response.json()["id"],
        "command": lambda **extra: _command(authenticated_client, session_id, **extra),
    }
