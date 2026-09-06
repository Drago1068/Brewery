"""Slice 13 — ListSessions compatibility for FRONTEND_E2E navigation."""

from __future__ import annotations

from fastapi.testclient import TestClient
from phase4_fixtures import started_fermentation  # noqa: F401

from brewing_api.application.auth import password_hash
from brewing_api.domain.identity.models import User
from brewing_api.main import app
from brewing_api.platform.database import SessionLocal


def test_list_sessions_owner_index_includes_started_session(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    brew_id = started_fermentation["session_id"]

    response = client.get("/api/v1/fermentation-sessions")
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    match = next((item for item in body if item["id"] == session_id), None)
    assert match is not None
    assert match["brew_session_id"] == brew_id
    assert match["status"] == "ACTIVE"
    assert "revision" in match


def test_list_sessions_hides_foreign_owner(started_fermentation):
    """Foreign owner must not see another owner's fermentation sessions."""
    session_id = started_fermentation["fermentation_session_id"]
    with SessionLocal() as db:
        db.add(
            User(
                username="slice13-other",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()

    with TestClient(app) as other:
        other.headers["Origin"] = "http://testserver"
        login = other.post(
            "/api/v1/auth/login",
            json={"username": "slice13-other", "password": "other-password-not-a-secret"},
        )
        assert login.status_code == 200, login.text
        other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        listed = other.get("/api/v1/fermentation-sessions")
        assert listed.status_code == 200, listed.text
        assert listed.json() == []
        detail = other.get(f"/api/v1/fermentation-sessions/{session_id}")
        assert detail.status_code == 404, detail.text
