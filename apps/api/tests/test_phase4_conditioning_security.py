"""Slice 5 security and PostgreSQL concurrency for conditioning handoff."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from brewing_api.application.auth import password_hash
from brewing_api.application.errors import ConflictError
from brewing_api.application.phase4.conditioning import ConditioningCommand, start_conditioning
from brewing_api.domain.fermentation.models import FermentationSession, FermentationStageInstance
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal

from phase4_fixtures import started_fermentation  # noqa: F401
from phase4_lifecycle_helpers import (
    reach_fermentation_complete,
    set_plan_conditioning,
    start_conditioning as http_start_conditioning,
)

pytestmark = pytest.mark.integration


def test_cross_session_conditioning_denied(started_fermentation, client):
    owner = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id)
    payload = reach_fermentation_complete(owner, started_fermentation)

    with SessionLocal() as db:
        db.add(
            User(
                username="other-conditioning-user",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "other-conditioning-user", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

    start = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/start-conditioning",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": payload["revision"]},
    )
    assert start.status_code == 404, start.text

    complete = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/complete-conditioning",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": payload["revision"]},
    )
    assert complete.status_code == 404, complete.text


def test_mass_assignment_and_forged_fields_rejected(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id)
    payload = reach_fermentation_complete(client, started_fermentation)
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/start-conditioning",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": payload["revision"],
            "status": "CONDITIONING_COMPLETE",
            "conditioning_mode": "LAGERING",
        },
    )
    # Pydantic v2 default ignores extras unless forbid; ensure no status forge
    if response.status_code == 200:
        assert response.json()["status"] == "CONDITIONING"
        assert response.json()["conditioning_mode"] == "COLD_CONDITIONING"
    else:
        assert response.status_code == 422


@pytest.mark.skipif(
    os.environ.get("TEST_USE_POSTGRES") != "1",
    reason="Slice 5 concurrency requires PostgreSQL",
)
def test_concurrent_start_conditioning_one_winner(started_fermentation):
    client = started_fermentation["client"]
    session_id = uuid.UUID(started_fermentation["fermentation_session_id"])
    set_plan_conditioning(session_id=str(session_id))
    payload = reach_fermentation_complete(client, started_fermentation)
    revision = payload["revision"]

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "brewer"))
        assert user is not None
        user_id = user.id

    barrier = threading.Barrier(2, timeout=10)

    def worker(operation_id: str):
        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                assert user is not None
                barrier.wait()
                session = start_conditioning(
                    db,
                    user,
                    session_id,
                    ConditioningCommand(
                        operation_id=operation_id,
                        expected_revision=revision,
                    ),
                )
                return ("ok", session.status, session.revision)
        except ConflictError as exc:
            return ("conflict", exc.code, None)
        except Exception as exc:  # noqa: BLE001
            return ("error", str(exc), None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, "race-start-cond-a"),
            pool.submit(worker, "race-start-cond-b"),
        ]
        results = [f.result(timeout=30) for f in futures]

    oks = [r for r in results if r[0] == "ok"]
    conflicts = [r for r in results if r[0] == "conflict"]
    assert len(oks) == 1, results
    assert len(conflicts) == 1, results
    assert oks[0][1] == "CONDITIONING"
    assert conflicts[0][1] in {"STALE_REVISION", "INVALID_TRANSITION", "STAGE_REPEAT_PROHIBITED"}

    with SessionLocal() as db:
        stages = list(
            db.scalars(
                select(FermentationStageInstance).where(
                    FermentationStageInstance.fermentation_session_id == session_id,
                    FermentationStageInstance.canonical_stage_type == "CONDITIONING",
                )
            ).all()
        )
        assert len(stages) == 1
        session = db.get(FermentationSession, session_id)
        assert session.status == "CONDITIONING"


@pytest.mark.skipif(
    os.environ.get("TEST_USE_POSTGRES") != "1",
    reason="Slice 5 concurrency requires PostgreSQL",
)
def test_idempotent_http_retry_after_success(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id)
    payload = reach_fermentation_complete(client, started_fermentation)
    op = "retry-after-handoff-success"
    first = http_start_conditioning(
        client, session_id=session_id, revision=payload["revision"], operation_id=op
    )
    assert first.status_code == 200, first.text
    second = http_start_conditioning(
        client, session_id=session_id, revision=payload["revision"], operation_id=op
    )
    assert second.status_code == 200, second.text
    assert second.json()["revision"] == first.json()["revision"]
    assert second.json()["status"] == "CONDITIONING"
