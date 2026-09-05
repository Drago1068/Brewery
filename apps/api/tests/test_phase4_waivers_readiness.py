"""Slice 11 — WAIVERS_READINESS (P4-FR-059/060, AC-051/054/059, ADV-008/035)."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from brewing_api.application.auth import password_hash
from brewing_api.application.phase4.plan import phase4_requirement_template_id
from brewing_api.domain.brew_sessions.models import BrewSession
from brewing_api.domain.fermentation.constants import REMINDER_SCHEMA_VERSION
from brewing_api.domain.fermentation.models import (
    FermentationCompletionAssessment,
    FermentationJournalEvent,
    FermentationOgConsumption,
    FermentationPlanSnapshot,
    FermentationReminder,
    FermentationSession,
    FermentationWaiver,
)
from brewing_api.domain.identity.models import User
from brewing_api.main import app
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now
from phase4_lifecycle_helpers import (
    reach_fermentation_complete,
    skip_conditioning,
)

pytestmark = pytest.mark.integration


def _revision(client, session_id: str) -> int:
    return client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]


def _force_og_unknown(session_id: str) -> None:
    with SessionLocal() as db:
        pin = db.scalar(
            select(FermentationOgConsumption).where(
                FermentationOgConsumption.fermentation_session_id == uuid.UUID(session_id),
                FermentationOgConsumption.is_current.is_(True),
            )
        )
        assert pin is not None
        pin.og_availability = "UNKNOWN"
        pin.og_sg = None
        pin.source_measurement_id = None
        pin.source_leaf_id = None
        db.commit()


def _reach_conditioning_complete(client, started: dict) -> dict:
    payload = reach_fermentation_complete(client, started)
    response = skip_conditioning(
        client,
        session_id=started["fermentation_session_id"],
        revision=payload["revision"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CONDITIONING_COMPLETE"
    return response.json()


def _insert_waivable_gravity_checkpoint(session_id: str, stage_id: str) -> str:
    """Extra waivable gravity checkpoint (not FERMENTATION_GRAVITY_STABILITY)."""
    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        brew = db.get(BrewSession, session.brew_session_id)
        assert session is not None and brew is not None
        template_id = phase4_requirement_template_id(
            brew.recipe_version_id, "FERMENTATION_PH", "default"
        )
        snapshot = db.scalar(
            select(FermentationPlanSnapshot).where(
                FermentationPlanSnapshot.fermentation_session_id == session.id
            )
        )
        assert snapshot is not None
        payload = dict(snapshot.payload or {})
        templates = list(payload.get("requirement_templates") or [])
        if not any(t.get("requirement_class") == "FERMENTATION_PH" for t in templates):
            templates.append(
                {
                    "requirement_template_id": str(template_id),
                    "requirement_class": "FERMENTATION_PH",
                    "stable_source": "default",
                    "required": True,
                    "waivable": True,
                }
            )
            payload["requirement_templates"] = templates
            snapshot.payload = payload
            flag_modified(snapshot, "payload")
        reminder = FermentationReminder(
            fermentation_session_id=session.id,
            stage_instance_id=uuid.UUID(stage_id),
            reminder_type="gravity_reading",
            message="Optional gravity checkpoint",
            status="DUE",
            due_at=utc_now(),
            requirement_class="FERMENTATION_PH",
            requirement_template_id=template_id,
            activation_ordinal=99,
            priority="OPTIONAL",
            waivable=True,
            schema_version=REMINDER_SCHEMA_VERSION,
        )
        db.add(reminder)
        db.commit()
        return str(reminder.id)


def test_ac054_adv008_non_waivable_prohibited(started_fermentation):
    """P4-AC-054 / P4-ADV-008 / P4-FR-060."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    for key in ("pitched_at", "yeast_addition_note", "ownership", "idempotency"):
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/waivers",
            json={
                "operation_id": str(uuid.uuid4()),
                "requirement_class": key,
                "reason": "Attempt to waive a non-waivable platform invariant field",
                "expected_revision": _revision(client, session_id),
            },
        )
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "WAIVER_PROHIBITED"
    with SessionLocal() as db:
        count = len(
            list(
                db.scalars(
                    select(FermentationWaiver).where(
                        FermentationWaiver.fermentation_session_id == uuid.UUID(session_id)
                    )
                ).all()
            )
        )
        assert count == 0


def test_fr060_stability_class_not_waivable(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    gravity = next(r for r in detail["reminders"] if r["reminder_type"] == "gravity_reading")
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/waivers",
        json={
            "operation_id": str(uuid.uuid4()),
            "requirement_id": gravity["id"],
            "reason": "Attempt to waive primary gravity stability requirement class",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "WAIVER_PROHIBITED"


def test_ac051_waiver_vs_later_gravity_supersession(started_fermentation):
    """P4-AC-051: ACK≠SATISFIED; evidence supersedes waiver; one satisfaction source."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    checkpoint_id = _insert_waivable_gravity_checkpoint(session_id, stage_id)

    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    primary = next(r for r in detail["reminders"] if r["id"] != checkpoint_id)
    ack = client.post(
        f"/api/v1/fermentation-sessions/reminders/{primary['id']}/acknowledge",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": _revision(client, session_id)},
    )
    assert ack.status_code == 200, ack.text
    ack_body = ack.json()
    assert ack_body["status"] == "ACKNOWLEDGED"
    assert ack_body["is_satisfied"] is False

    waived = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/waivers",
        json={
            "operation_id": str(uuid.uuid4()),
            "requirement_id": checkpoint_id,
            "reason": "Waive optional gravity checkpoint pending instrument availability",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert waived.status_code == 201, waived.text
    waiver_id = waived.json()["id"]
    assert waived.json()["status"] == "ACTIVE"

    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    checkpoint = next(r for r in detail["reminders"] if r["id"] == checkpoint_id)
    assert checkpoint["status"] == "SKIPPED"
    assert checkpoint["is_satisfied"] is False
    assert checkpoint["satisfaction_source_type"] == "FermentationWaiver"

    measured = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.020",
            "unit": "SG",
            "observed_at": datetime.now(UTC).isoformat(),
            "stage_instance_id": stage_id,
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert measured.status_code == 201, measured.text
    measurement_id = measured.json()["id"]

    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    checkpoint = next(r for r in detail["reminders"] if r["id"] == checkpoint_id)
    assert checkpoint["status"] == "COMPLETED"
    assert checkpoint["is_satisfied"] is True
    assert checkpoint["satisfaction_source_type"] == "FermentationMeasurement"
    assert checkpoint["satisfaction_source_id"] == measurement_id
    waiver = next(w for w in detail["waivers"] if w["id"] == waiver_id)
    assert waiver["status"] == "SUPERSEDED_BY_EVIDENCE"
    assert waiver["superseded_by_evidence_id"] == measurement_id


def test_ac059_adv035_og_unknown_readiness_waiver_and_override(started_fermentation):
    """P4-AC-059 / P4-ADV-035 / P4-FR-059."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_conditioning_complete(client, started_fermentation)
    _force_og_unknown(session_id)

    # (a) assess without waiver → not READY
    assess_a = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/assess-packaging-readiness",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": _revision(client, session_id)},
    )
    assert assess_a.status_code == 200, assess_a.text
    body_a = assess_a.json()
    assert body_a["status"] == "CONDITIONING_COMPLETE"
    assessment_a = body_a["packaging_readiness_assessment"]
    assert assessment_a["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert assessment_a["predicate_results"]["readiness_status"] == "NOT_READY"

    # ADV-035 / AC-059(a): cannot get READY without waiver
    templates = body_a["plan_snapshot"]["payload"]["requirement_templates"]
    og_template = next(t for t in templates if t["requirement_class"] == "ORIGINAL_GRAVITY_KNOWN")

    # (b) waive ORIGINAL_GRAVITY_KNOWN then assess + handoff → READY_WITH_WAIVERS
    waived = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/waivers",
        json={
            "operation_id": str(uuid.uuid4()),
            "requirement_id": og_template["requirement_template_id"],
            "reason": "Owner accepts unknown OG for packaging readiness with explicit waiver",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert waived.status_code == 201, waived.text
    assert waived.json()["effect"] == "READINESS_R3_WAIVED"

    assess_b = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/assess-packaging-readiness",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": _revision(client, session_id)},
    )
    assert assess_b.status_code == 200, assess_b.text
    body_b = assess_b.json()
    assert body_b["status"] == "COMPLETION_ASSESSED"
    assessment_b = body_b["packaging_readiness_assessment"]
    assert assessment_b["predicate_results"]["readiness_status"] == "READY_WITH_WAIVERS"

    handoff = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/record-packaging-readiness-handoff",
        json={
            "operation_id": str(uuid.uuid4()),
            "assessment_id": assessment_b["id"],
            "expected_revision": _revision(client, session_id),
        },
    )
    assert handoff.status_code == 200, handoff.text
    assert handoff.json()["status"] == "HANDOFF_READY"
    assert handoff.json()["packaging_readiness_handoff"]["readiness_status"] == "READY_WITH_WAIVERS"

    # (c) / ADV-035: override while R1 false → 409 OVERRIDE_PROHIBITED
    with SessionLocal() as db:
        ferm = db.scalar(
            select(FermentationCompletionAssessment).where(
                FermentationCompletionAssessment.fermentation_session_id == uuid.UUID(session_id),
                FermentationCompletionAssessment.assessment_kind == "FERMENTATION",
                FermentationCompletionAssessment.is_current.is_(True),
            )
        )
        assert ferm is not None
        ferm.invalidated_at = utc_now()
        ferm.outcome = "COMPLETION_INVALIDATED"
        db.commit()

    assess_c = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/assess-packaging-readiness",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
            "override": True,
            "override_reason": "Attempt readiness override while fermentation R1 is false",
        },
    )
    assert assess_c.status_code == 409, assess_c.text
    assert assess_c.json()["code"] == "OVERRIDE_PROHIBITED"
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(FermentationCompletionAssessment).where(
                    FermentationCompletionAssessment.fermentation_session_id
                    == uuid.UUID(session_id),
                    FermentationCompletionAssessment.assessment_kind == "PACKAGING",
                    FermentationCompletionAssessment.outcome == "INSUFFICIENT_EVIDENCE",
                )
            ).all()
        )
        assert len(rows) >= 1


def test_fr059_og_waiver_idempotent_replay(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_conditioning_complete(client, started_fermentation)
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    og_template = next(
        t
        for t in detail["plan_snapshot"]["payload"]["requirement_templates"]
        if t["requirement_class"] == "ORIGINAL_GRAVITY_KNOWN"
    )
    op_id = str(uuid.uuid4())
    payload = {
        "operation_id": op_id,
        "requirement_id": og_template["requirement_template_id"],
        "reason": "Idempotent readiness waiver replay proof for ORIGINAL_GRAVITY_KNOWN",
        "expected_revision": _revision(client, session_id),
    }
    first = client.post(f"/api/v1/fermentation-sessions/{session_id}/waivers", json=payload)
    assert first.status_code == 201, first.text
    replay = client.post(f"/api/v1/fermentation-sessions/{session_id}/waivers", json=payload)
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == first.json()["id"]
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(FermentationWaiver).where(
                    FermentationWaiver.fermentation_session_id == uuid.UUID(session_id),
                    FermentationWaiver.requirement_class == "ORIGINAL_GRAVITY_KNOWN",
                )
            ).all()
        )
        assert len(rows) == 1


def test_fr059_cross_owner_waiver_404(started_fermentation, client):
    owner = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_conditioning_complete(owner, started_fermentation)
    with SessionLocal() as db:
        db.add(
            User(
                username="slice11-other",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "slice11-other", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    denied = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/waivers",
        json={
            "operation_id": str(uuid.uuid4()),
            "requirement_class": "ORIGINAL_GRAVITY_KNOWN",
            "reason": "Cross-owner attempt must nondisclose session existence",
        },
    )
    assert denied.status_code == 404


def test_fr059_recovery_reread_waiver_and_handoff(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_conditioning_complete(client, started_fermentation)
    _force_og_unknown(session_id)
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    og_template = next(
        t
        for t in detail["plan_snapshot"]["payload"]["requirement_templates"]
        if t["requirement_class"] == "ORIGINAL_GRAVITY_KNOWN"
    )
    client.post(
        f"/api/v1/fermentation-sessions/{session_id}/waivers",
        json={
            "operation_id": str(uuid.uuid4()),
            "requirement_id": og_template["requirement_template_id"],
            "reason": "Recovery proof waiver for ORIGINAL_GRAVITY_KNOWN readiness",
            "expected_revision": _revision(client, session_id),
        },
    )
    assessed = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/assess-packaging-readiness",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": _revision(client, session_id)},
    )
    assert assessed.status_code == 200
    assessment_id = assessed.json()["packaging_readiness_assessment"]["id"]
    client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/record-packaging-readiness-handoff",
        json={
            "operation_id": str(uuid.uuid4()),
            "assessment_id": assessment_id,
            "expected_revision": _revision(client, session_id),
        },
    )
    expected = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    with TestClient(app) as fresh:
        fresh.headers["Origin"] = "http://testserver"
        login = fresh.post(
            "/api/v1/auth/login",
            json={"username": "brewer", "password": "test-password-not-a-secret"},
        )
        fresh.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        reread = fresh.get(f"/api/v1/fermentation-sessions/{session_id}")
        assert reread.status_code == 200
        body = reread.json()
        assert body["waivers"] == expected["waivers"]
        assert body["packaging_readiness_handoff"] == expected["packaging_readiness_handoff"]
        assert body["status"] == "HANDOFF_READY"


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("TEST_USE_POSTGRES") != "1",
    reason="Slice 11 concurrency requires PostgreSQL",
)
def test_fr059_concurrent_og_waiver_one_active(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_conditioning_complete(client, started_fermentation)
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    og_template = next(
        t
        for t in detail["plan_snapshot"]["payload"]["requirement_templates"]
        if t["requirement_class"] == "ORIGINAL_GRAVITY_KNOWN"
    )
    barrier = threading.Barrier(2)
    results: list[int] = []

    def worker() -> None:
        barrier.wait()
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/waivers",
            json={
                "operation_id": str(uuid.uuid4()),
                "requirement_id": og_template["requirement_template_id"],
                "reason": "Concurrent ORIGINAL_GRAVITY_KNOWN waiver race participant",
                "expected_revision": _revision(client, session_id),
            },
        )
        results.append(response.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker), pool.submit(worker)]
        for future in futures:
            future.result()

    assert 201 in results
    assert any(code in {409, 201} for code in results)
    with SessionLocal() as db:
        active = list(
            db.scalars(
                select(FermentationWaiver).where(
                    FermentationWaiver.fermentation_session_id == uuid.UUID(session_id),
                    FermentationWaiver.status == "ACTIVE",
                    FermentationWaiver.requirement_class == "ORIGINAL_GRAVITY_KNOWN",
                )
            ).all()
        )
        assert len(active) == 1
        events = list(
            db.scalars(
                select(FermentationJournalEvent).where(
                    FermentationJournalEvent.fermentation_session_id == uuid.UUID(session_id),
                    FermentationJournalEvent.event_type == "FERMENTATION_WAIVER_RECORDED",
                )
            ).all()
        )
        assert len(events) == 1
