"""Phase 4 final-acceptance cross-cutting campaigns (security / idempotency / AI / concurrency)."""
# ruff: noqa: F811 - test parameters intentionally shadow the fixture import

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from phase4_fixtures import started_fermentation  # noqa: F401
from sqlalchemy import inspect

from brewing_api.application.auth import password_hash
from brewing_api.domain.identity.models import User
from brewing_api.main import app
from brewing_api.platform.database import SessionLocal, engine

pytestmark = pytest.mark.integration


def test_fa_security_missing_operation_id_rejected(started_fermentation):
    """P4-FR-071 — mutation without operation_id must fail closed."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    revision = started_fermentation["fermentation_revision"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"expected_revision": revision},
    )
    assert response.status_code == 422, response.text
    after = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert after.json()["revision"] == revision


def test_fa_security_csrf_missing_and_wrong_on_ferment_mutate(started_fermentation):
    """P4-FR-076 / P4-AC-039 / P4-ADV-014 — CSRF on Phase 4 mutating route."""
    owner = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    revision = owner.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]
    token = owner.headers.get("X-CSRF-Token")
    owner.headers.pop("X-CSRF-Token", None)
    missing = owner.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert missing.status_code == 403, missing.text
    assert missing.json()["code"] == "CSRF_REJECTED"
    owner.headers["X-CSRF-Token"] = "wrong-csrf-token"
    wrong = owner.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert wrong.status_code == 403
    assert wrong.json()["code"] == "CSRF_REJECTED"
    owner.headers["X-CSRF-Token"] = token
    after = owner.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert after.json()["revision"] == revision


def test_fa_security_idor_nested_matrix(started_fermentation):
    """P4-FR-075 / P4-AC-038 / P4-ADV-003 — cross-owner nested IDOR → 404, no mutation."""
    owner = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    revision = owner.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]
    created = owner.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_TEMPERATURE",
            "value": "18.0",
            "unit": "degC",
            "method": "PROBE",
            "observed_at": datetime.now(UTC).isoformat(),
            "stage_instance_id": stage_id,
            "expected_revision": revision,
            "source": "OBSERVED",
        },
    )
    assert created.status_code == 201, created.text
    measurement_id = created.json()["id"]
    other_username = f"fa-other-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(
            User(
                username=other_username,
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    # Separate client so owner session cookies are not overwritten.
    with TestClient(app) as other:
        other.headers["Origin"] = "http://testserver"
        login = other.post(
            "/api/v1/auth/login",
            json={"username": other_username, "password": "other-password-not-a-secret"},
        )
        assert login.status_code == 200
        other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        assert other.get(f"/api/v1/fermentation-sessions/{session_id}").status_code == 404
        mutate = other.post(
            f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
            json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
        )
        assert mutate.status_code == 404
        nested = other.post(
            f"/api/v1/fermentation-sessions/{session_id}/measurements/{measurement_id}/corrections",
            json={
                "operation_id": str(uuid.uuid4()),
                "correction_of_id": measurement_id,
                "reason": "Cross-owner correction must be rejected without disclosure",
                "value": "19.0",
                "unit": "degC",
                "method": "PROBE",
            },
        )
        assert nested.status_code == 404
    owner_after = owner.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert owner_after.status_code == 200
    assert owner_after.json()["status"] == "ACTIVE"


def test_fa_idempotency_pause_replay_and_conflict(started_fermentation):
    """P4-FR-072 — phase4-operation-v1 replay + key reuse conflict."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    revision = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]
    op = str(uuid.uuid4())
    first = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": op, "expected_revision": revision},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": op, "expected_revision": revision},
    )
    assert second.status_code == 200, second.text
    assert second.json()["revision"] == first.json()["revision"]
    assert second.json()["status"] == first.json()["status"]
    conflict = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": op, "expected_revision": revision + 99},
    )
    assert conflict.status_code == 409


def test_fa_concurrency_dual_pause_one_winner(started_fermentation):
    """Final concurrency gate: two distinct pause keys → exactly one pause effect."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    before = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    revision = before["revision"]
    csrf = client.headers.get("X-CSRF-Token")
    cookies = client.cookies

    def worker(operation_id: str) -> int:
        with TestClient(app) as local:
            local.headers["Origin"] = "http://testserver"
            local.headers["X-CSRF-Token"] = csrf or ""
            local.cookies.update(cookies)
            response = local.post(
                f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
                json={"operation_id": operation_id, "expected_revision": revision},
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(worker, [str(uuid.uuid4()), str(uuid.uuid4())]))
    after = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert after["status"] == "PAUSED"
    # Exactly one authoritative pause: revision advances by 1 regardless of HTTP race timing.
    assert after["revision"] == revision + 1
    assert codes.count(200) >= 1
    if engine.dialect.name == "postgresql":
        assert codes.count(200) == 1
        assert any(code == 409 for code in codes)


def test_fa_ai_boundary_no_packaging_or_ai_authority_routes():
    """P4-FR-086 / §51 — Phase 5 packaging tables/routes absent; no AI mutate routes."""
    prohibited_substrings = (
        "packaging-sessions",
        "packaging_sessions",
        "/ai/",
        "/assistant/commit",
        "carbonation",
    )
    for route in app.routes:
        path = (getattr(route, "path", "") or "").lower()
        for needle in prohibited_substrings:
            assert needle not in path, path
    tables = set(inspect(engine).get_table_names())
    for prohibited in (
        "packaging_sessions",
        "keg_inventory",
        "carbonation_operations",
        "qa_qc_plans",
    ):
        assert prohibited not in tables
    with TestClient(app) as probe:
        probe.headers["Origin"] = "http://testserver"
        assert probe.post("/api/v1/packaging-sessions", json={}).status_code in {404, 405}
        assert probe.post("/api/v1/ai/measurements", json={}).status_code in {404, 405}
