"""Slice 3 security: lifecycle command ownership and IDOR."""

from __future__ import annotations

import uuid

from brewing_api.application.auth import password_hash
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal

from phase4_fixtures import started_fermentation  # noqa: F401

pytestmark = __import__("pytest").mark.integration


def test_cross_user_complete_fermentation_denied(started_fermentation, client):
    session_id = started_fermentation["fermentation_session_id"]
    with SessionLocal() as db:
        db.add(
            User(
                username="other-lifecycle-user",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "other-lifecycle-user", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/complete-fermentation",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": started_fermentation["fermentation_revision"],
        },
    )
    assert response.status_code == 404, response.text


def test_cross_user_pause_denied(started_fermentation, client):
    session_id = started_fermentation["fermentation_session_id"]
    with SessionLocal() as db:
        db.add(
            User(
                username="other-lifecycle-pause",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "other-lifecycle-pause", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": started_fermentation["fermentation_revision"],
        },
    )
    assert response.status_code == 404, response.text
