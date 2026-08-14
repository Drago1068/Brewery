import json
import uuid

from test_phase3_engines import PNG

from brewing_api.application.auth import password_hash
from brewing_api.domain.identity.models import User
from brewing_api.platform.config import get_settings
from brewing_api.platform.database import SessionLocal


def test_csrf_matrix_missing_wrong_and_valid(client, recipe_payload):
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "brewer", "password": "test-password-not-a-secret"},
    )
    assert login.status_code == 200
    token = login.json()["csrf_token"]
    client.headers.pop("X-CSRF-Token", None)
    missing = client.post("/api/v1/recipes", json=recipe_payload)
    assert missing.status_code == 403
    assert missing.json()["code"] == "CSRF_REJECTED"
    client.headers["X-CSRF-Token"] = "wrong-csrf-token"
    wrong = client.post("/api/v1/recipes", json=recipe_payload)
    assert wrong.status_code == 403
    assert wrong.json()["code"] == "CSRF_REJECTED"
    client.headers["X-CSRF-Token"] = token
    valid = client.post("/api/v1/recipes", json=recipe_payload)
    assert valid.status_code == 201


def test_cross_origin_header_is_rejected(authenticated_client, recipe_payload):
    authenticated_client.headers["Origin"] = "https://evil.example"
    response = authenticated_client.post("/api/v1/recipes", json=recipe_payload)
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_REJECTED"


def test_cross_owner_session_get_is_404(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    with SessionLocal() as db:
        db.add(
            User(
                username="other-brewer-sec",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "other-brewer-sec", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    hidden = client.get(f"/api/v1/brew-sessions/{session_id}")
    assert hidden.status_code == 404


def test_metrics_endpoint_does_not_leak_secrets(authenticated_client):
    response = authenticated_client.get("/api/v1/metrics/phase3")
    assert response.status_code == 200
    payload = json.dumps(response.json())
    settings = get_settings()
    assert settings.session_secret not in payload
    assert settings.bootstrap_admin_password not in payload
    assert "test-password-not-a-secret" not in payload
    assert settings.database_url not in payload
    reconstruct = authenticated_client.get(f"/api/v1/metrics/phase3/reconstruct/{uuid.uuid4().hex}")
    assert reconstruct.status_code == 200
    reconstructed = json.dumps(reconstruct.json())
    assert settings.session_secret not in reconstructed
    assert settings.bootstrap_admin_password not in reconstructed


def test_attachment_retrieval_requires_auth(active_mash, tmp_path, monkeypatch):
    from brewing_api.platform import config

    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    config.get_settings.cache_clear()
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    uploaded = client.post(
        f"/api/v1/brew-sessions/{session_id}/attachments",
        files={"file": ("mash.png", PNG, "image/png")},
        data={"operation_id": "sec-media-1"},
    )
    assert uploaded.status_code == 201
    attachment_id = uploaded.json()["id"]
    session_cookie = client.cookies.get("brewing_session")
    client.cookies.clear()
    denied = client.get(f"/api/v1/brew-sessions/{session_id}/attachments/{attachment_id}")
    assert denied.status_code == 401
    client.cookies.set("brewing_session", session_cookie)
    allowed = client.get(f"/api/v1/brew-sessions/{session_id}/attachments/{attachment_id}")
    assert allowed.status_code == 200


def test_metrics_requires_authentication(client):
    denied = client.get("/api/v1/metrics/phase3")
    assert denied.status_code == 401


def test_csrf_wrong_session_token_after_relogin(client, recipe_payload):
    first = client.post(
        "/api/v1/auth/login",
        json={"username": "brewer", "password": "test-password-not-a-secret"},
    )
    assert first.status_code == 200
    old_token = first.json()["csrf_token"]
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    second = client.post(
        "/api/v1/auth/login",
        json={"username": "brewer", "password": "test-password-not-a-secret"},
    )
    assert second.status_code == 200
    new_token = second.json()["csrf_token"]
    assert new_token != old_token
    client.headers["X-CSRF-Token"] = old_token
    rejected = client.post("/api/v1/recipes", json=recipe_payload)
    assert rejected.status_code == 403
    assert rejected.json()["code"] == "CSRF_REJECTED"
    client.headers["X-CSRF-Token"] = new_token
    allowed = client.post("/api/v1/recipes", json={**recipe_payload, "name": "CSRF Rotation Ale"})
    assert allowed.status_code == 201


def test_mass_assignment_cannot_set_measurement_provenance(active_mash):
    client = active_mash["client"]
    response = client.post(
        f"/api/v1/brew-sessions/stages/{active_mash['stage_id']}/measurements",
        json={
            "measurement_type": "MASH_PH",
            "value": "5.30",
            "unit": "pH",
            "provenance": "SYSTEM",
            "actor_user_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 201
    with SessionLocal() as db:
        from brewing_api.domain.measurements.models import Measurement

        row = db.get(Measurement, uuid.UUID(response.json()["id"]))
        assert row.provenance == "BREWER"


def test_sql_injection_session_id_is_rejected(authenticated_client):
    response = authenticated_client.get("/api/v1/brew-sessions/not-a-uuid'; drop table users;--")
    assert response.status_code == 422


def test_error_handler_does_not_leak_exception_text(authenticated_client):
    response = authenticated_client.get(f"/api/v1/brew-sessions/{uuid.uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "traceback" not in str(body).lower()
    assert "psycopg" not in str(body).lower()
    assert "sqlalchemy" not in str(body).lower()
