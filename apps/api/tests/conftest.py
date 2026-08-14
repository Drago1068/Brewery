import os
import re
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

from brewing_api.application.phase3.csrf import reset_rate_limits
from brewing_api.domain import model_registry  # noqa: F401
from brewing_api.main import app
from brewing_api.platform.database import Base, engine


@pytest.fixture(autouse=True)
def clean_database():
    reset_rate_limits()
    if os.environ.get("TEST_USE_POSTGRES") == "1":
        from sqlalchemy import text

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE brew_sessions "
                    "SET status = 'ABORTED', aborted_at = NOW(), abort_reason = 'pytest cleanup' "
                    "WHERE status IN ('ACTIVE', 'PAUSED')"
                )
            )
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


def _inject_phase3_command(test_client: TestClient, original_get, path: str, kwargs: dict) -> None:
    if "/auth/" in path:
        return
    if kwargs.get("files") is not None or (
        kwargs.get("data") is not None and "json" not in kwargs
    ):
        return
    body = kwargs.get("json")
    if body is None:
        kwargs["json"] = body = {}
    if not isinstance(body, dict):
        return
    body.setdefault("operation_id", str(uuid.uuid4()))
    if "expected_revision" in body:
        return
    needs_revision = bool(
        re.search(
            r"/(pause|resume|abort|repeat|return|skip|extend|complete)(/|$)"
            r"|/mash/start|/stages/.+/start|/stages/.+/timers|/timers/",
            path,
        )
    )
    if not needs_revision:
        return
    session_id = None
    match = re.search(r"/brew-sessions/([0-9a-fA-F-]{36})", path)
    if match:
        session_id = match.group(1)
    got = None
    if session_id:
        got = original_get(f"/api/v1/brew-sessions/{session_id}")
    else:
        got = original_get("/api/v1/brew-sessions/active")
    if got is not None and got.status_code == 200:
        payload = got.json()
        if payload and payload.get("revision") is not None:
            body["expected_revision"] = payload["revision"]


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        test_client.headers["Origin"] = "http://testserver"
        original_post = test_client.post
        original_get = test_client.get

        def post_with_csrf(*args, **kwargs):
            path = str(args[0]) if args else ""
            _inject_phase3_command(test_client, original_get, path, kwargs)
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


@pytest.fixture
def active_mash(authenticated_client: TestClient, recipe_payload: dict):
    existing = authenticated_client.get("/api/v1/brew-sessions/active")
    if existing.status_code == 200:
        body = existing.json()
        if body and body.get("id"):
            aborted = authenticated_client.post(
                f"/api/v1/brew-sessions/{body['id']}/abort",
                json={"reason": "Clearing prior test brew session before fixture"},
            )
            assert aborted.status_code == 200, aborted.text

    recipe = authenticated_client.post("/api/v1/recipes", json=recipe_payload).json()
    session_response = authenticated_client.post(
        "/api/v1/brew-sessions", json={"recipe_version_id": recipe["version_id"]}
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]
    started = authenticated_client.post(f"/api/v1/brew-sessions/{session_id}/start")
    assert started.status_code == 200, started.text
    mash_response = authenticated_client.post(f"/api/v1/brew-sessions/{session_id}/mash/start")
    assert mash_response.status_code == 200, mash_response.text
    return {
        "client": authenticated_client,
        "recipe": recipe,
        "session_id": session_id,
        "stage_id": mash_response.json()["id"],
    }
