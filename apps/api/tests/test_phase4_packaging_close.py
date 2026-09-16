"""Slice 12 — PACKAGING_READINESS_CLOSE (FR-008/013/015/022/043/044/074/089, AC-007/011/017/025/026/047/058/061, ADV-012/023/033)."""  # noqa: E501

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from phase4_lifecycle_helpers import (
    reach_fermentation_complete,
    skip_conditioning,
)
from sqlalchemy import func, select, text

from brewing_api.domain.fermentation.models import (
    FermentationCompletionAssessment,
    FermentationJournalEvent,
    FermentationMeasurement,
    FermentationSession,
    PackagingReadinessHandoff,
)
from brewing_api.domain.inventory.models import InventoryTransaction
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now

pytestmark = pytest.mark.integration

_CORRECTION_REASON = "Corrected hydrometer reading after reviewing lab notes from yesterday"


def _revision(client, session_id: str) -> int:
    return client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]


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


def _assess(client, session_id: str, *, override: bool = False, reason: str | None = None) -> dict:
    body = {
        "operation_id": str(uuid.uuid4()),
        "expected_revision": _revision(client, session_id),
        "override": override,
    }
    if reason is not None:
        body["override_reason"] = reason
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/assess-packaging-readiness",
        json=body,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _record_handoff(client, session_id: str, assessment_id: str) -> dict:
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/record-packaging-readiness-handoff",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
            "assessment_id": assessment_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _reach_handoff_ready(client, started: dict) -> dict:
    _reach_conditioning_complete(client, started)
    session_id = started["fermentation_session_id"]
    assessed = _assess(client, session_id)
    assessment_id = assessed["packaging_readiness_assessment"]["id"]
    handoff = _record_handoff(client, session_id, assessment_id)
    assert handoff["status"] == "HANDOFF_READY"
    return handoff


def _close(
    client, session_id: str, *, operation_id: str | None = None, revision: int | None = None
):
    return client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/close",
        json={
            "operation_id": operation_id or str(uuid.uuid4()),
            "expected_revision": revision
            if revision is not None
            else _revision(client, session_id),
        },
    )


def _latest_gravity_id(session_id: str) -> str:
    with SessionLocal() as db:
        row = db.scalar(
            select(FermentationMeasurement)
            .where(
                FermentationMeasurement.fermentation_session_id == uuid.UUID(session_id),
                FermentationMeasurement.measurement_type == "FERMENTATION_GRAVITY",
            )
            .order_by(FermentationMeasurement.observed_at.desc())
            .limit(1)
        )
        assert row is not None
        return str(row.id)


def _reanchor_gravities_after_pitch(session_id: str) -> None:
    """Move pitch/stage/gravity chronology so CLOSED corrections keep valid windows."""
    from datetime import timedelta

    from brewing_api.application.phase4.derived_gravity import recompute_derived_gravity
    from brewing_api.application.phase4.time_validation import _coerce_aware
    from brewing_api.domain.fermentation.models import (
        FermentationStageInstance,
        FermentationYeastPitchReference,
    )

    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        pitch = db.scalar(
            select(FermentationYeastPitchReference).where(
                FermentationYeastPitchReference.fermentation_session_id == session.id
            )
        )
        assert session is not None and pitch is not None
        now = utc_now()
        pitch.pitched_at = _coerce_aware(now - timedelta(days=4))
        if session.started_at is not None:
            session.started_at = pitch.pitched_at + timedelta(hours=1)
        base = pitch.pitched_at + timedelta(hours=2)
        stage = db.scalar(
            select(FermentationStageInstance).where(
                FermentationStageInstance.fermentation_session_id == session.id,
                FermentationStageInstance.canonical_stage_type == "ACTIVE_FERMENTATION",
            )
        )
        if stage is not None:
            stage.first_started_at = base - timedelta(hours=1)
            stage.started_at = stage.first_started_at
            stage.current_activation_started_at = stage.first_started_at
            stage.first_completed_at = base + timedelta(hours=72)
            stage.completed_at = stage.first_completed_at
            stage.current_completed_at = stage.first_completed_at
        rows = list(
            db.scalars(
                select(FermentationMeasurement)
                .where(
                    FermentationMeasurement.fermentation_session_id == session.id,
                    FermentationMeasurement.measurement_type == "FERMENTATION_GRAVITY",
                )
                .order_by(FermentationMeasurement.observed_at.asc())
            ).all()
        )
        for index, row in enumerate(rows):
            row.observed_at = base + timedelta(hours=24 * index)
            row.recorded_at = row.observed_at + timedelta(minutes=5)
            row.late_entry = False
        if session.closed_at is not None:
            session.closed_at = base + timedelta(hours=80)
        recompute_derived_gravity(db, session.id)
        db.commit()


def test_ac011_fr013_handoff_zero_packaging_ledger(started_fermentation):
    """P4-AC-011 / P4-FR-013: readiness row only; zero packaging sessions / ledger consumption."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    body = _reach_handoff_ready(client, started_fermentation)
    handoff = body["packaging_readiness_handoff"]
    assert handoff["readiness_status"] in {"READY", "READY_WITH_WAIVERS"}
    assert handoff["is_current"] is True

    with SessionLocal() as db:
        handoff_count = db.scalar(select(func.count()).select_from(PackagingReadinessHandoff))
        assert handoff_count >= 1
        # No Phase 5 packaging aggregate tables exist; ledger consumption must stay zero for owner.
        owner_id = db.get(FermentationSession, uuid.UUID(session_id)).user_id
        consumption = db.scalar(
            select(func.count())
            .select_from(InventoryTransaction)
            .where(
                InventoryTransaction.owner_id == owner_id,
                InventoryTransaction.transaction_type == "CONSUMPTION",
            )
        )
        assert consumption == 0
        # Confirm no packaging_sessions table leakage.
        try:
            db.execute(text("SELECT COUNT(*) FROM packaging_sessions"))
            pytest.fail("packaging_sessions must not exist in Phase 4")
        except Exception:
            db.rollback()


def test_fr022_ac017_close_requires_ready_handoff(started_fermentation):
    """P4-FR-022 / P4-AC-017: NOT_READY current handoff → 409 HANDOFF_NOT_READY."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    with SessionLocal() as db:
        handoff = db.scalar(
            select(PackagingReadinessHandoff).where(
                PackagingReadinessHandoff.fermentation_session_id == uuid.UUID(session_id),
                PackagingReadinessHandoff.is_current.is_(True),
            )
        )
        assert handoff is not None
        handoff.readiness_status = "NOT_READY"
        db.commit()

    denied = _close(client, session_id)
    assert denied.status_code == 409, denied.text
    assert denied.json()["code"] == "HANDOFF_NOT_READY"
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert detail["status"] == "HANDOFF_READY"


def test_close_happy_path_and_idempotent_replay(started_fermentation):
    """P4-FR-022 close success + idempotent replay; FR-015 Close cell."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    op = str(uuid.uuid4())
    rev = _revision(client, session_id)
    first = _close(client, session_id, operation_id=op, revision=rev)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "CLOSED"
    assert first.json()["closed_at"] is not None

    replay = _close(client, session_id, operation_id=op, revision=rev)
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "CLOSED"
    assert replay.json()["closed_at"] == first.json()["closed_at"]

    with SessionLocal() as db:
        events = list(
            db.scalars(
                select(FermentationJournalEvent).where(
                    FermentationJournalEvent.fermentation_session_id == uuid.UUID(session_id),
                    FermentationJournalEvent.event_type == "FERMENTATION_SESSION_CLOSED",
                )
            ).all()
        )
        assert len(events) == 1


def test_ac007_adv023_fr008_second_start_after_closed(started_fermentation):
    """P4-AC-007 / P4-ADV-023 / P4-FR-008: CLOSED then second start → 409 EXISTS."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    brew_id = started_fermentation["session_id"]
    _reach_handoff_ready(client, started_fermentation)
    closed = _close(client, session_id)
    assert closed.status_code == 200, closed.text

    second = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "FERMENTATION_SESSION_EXISTS"


def test_adv033_abort_from_handoff_ready_denied(started_fermentation):
    """P4-ADV-033: HANDOFF_READY abort → 409 INVALID_TRANSITION."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    aborted = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/abort",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
            "reason": "Attempted abort after packaging readiness handoff recorded",
        },
    )
    assert aborted.status_code == 409, aborted.text
    assert aborted.json()["code"] == "INVALID_TRANSITION"
    assert (
        client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["status"]
        == "HANDOFF_READY"
    )


def test_ac058_assess_after_f1_fail_from_handoff_ready(started_fermentation):
    """P4-AC-058: HANDOFF_READY + F1-failing evidence → Assess → COMPLETION_ASSESSED + INVALIDATED."""  # noqa: E501
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)

    # Completion-affecting gravity state that makes F1 fail while remaining HANDOFF_READY
    # for the §9.4 Assess path (assessment-row R1 becomes false).
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

    assessed = _assess(client, session_id)
    assert assessed["status"] == "COMPLETION_ASSESSED"
    handoff = assessed["packaging_readiness_handoff"]
    assert handoff["readiness_status"] == "INVALIDATED"
    assert handoff["invalidated_at"] is not None


def test_ac025_closed_correction_invalidates_handoff_stays_closed(started_fermentation):
    """P4-AC-025 / P4-FR-043: CLOSED + completion-affecting correction → stay CLOSED, handoff INVALIDATED."""  # noqa: E501
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    closed = _close(client, session_id)
    assert closed.status_code == 200, closed.text
    _reanchor_gravities_after_pitch(session_id)
    gravity_id = _latest_gravity_id(session_id)

    corrected = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{gravity_id}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": gravity_id,
            "reason": _CORRECTION_REASON,
            "value": "1.050",
            "unit": "SG",
            "method": "HYDROMETER",
        },
    )
    assert corrected.status_code == 201, corrected.text
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert detail["status"] == "CLOSED"
    assert detail["packaging_readiness_handoff"] is None or detail[
        "packaging_readiness_handoff"
    ].get("is_current") in {False, None}

    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        assert session.status == "CLOSED"
        assert session.fermentation_current_completed_at is not None
        current = db.scalar(
            select(PackagingReadinessHandoff).where(
                PackagingReadinessHandoff.fermentation_session_id == session.id,
                PackagingReadinessHandoff.is_current.is_(True),
            )
        )
        assert current is None
        prior = db.scalar(
            select(PackagingReadinessHandoff)
            .where(PackagingReadinessHandoff.fermentation_session_id == session.id)
            .order_by(PackagingReadinessHandoff.handoff_version.desc())
            .limit(1)
        )
        assert prior is not None
        assert prior.readiness_status == "INVALIDATED"
        assert prior.is_current is False


def test_ac026_ac061_fr089_closed_requalify_new_handoff_version(started_fermentation):
    """P4-AC-026 / P4-AC-061 / P4-FR-089: CLOSED requalify from current evidence; handoff v2; stay CLOSED."""  # noqa: E501
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    closed = _close(client, session_id)
    assert closed.status_code == 200, closed.text

    _reanchor_gravities_after_pitch(session_id)
    gravity_id = _latest_gravity_id(session_id)
    # Small correction still within stable window so R1 remains true from current evidence.
    corrected = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{gravity_id}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": gravity_id,
            "reason": _CORRECTION_REASON,
            "value": "1.0185",
            "unit": "SG",
            "method": "HYDROMETER",
        },
    )
    assert corrected.status_code == 201, corrected.text
    assert client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["status"] == "CLOSED"

    assessed = _assess(client, session_id)
    assert assessed["status"] == "CLOSED"
    assessment = assessed["packaging_readiness_assessment"]
    assert assessment["predicate_results"]["R1"]["evaluation_mode"] == "CURRENT_EVIDENCE"
    assert assessment["predicate_results"]["R1"]["passed"] is True
    assert assessment["predicate_results"]["R2"]["passed"] is True

    # Prove no CompleteFermentation/CompleteConditioning after CLOSED.
    complete_denied = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/complete-fermentation",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert complete_denied.status_code == 409, complete_denied.text

    handoff_body = _record_handoff(client, session_id, assessment["id"])
    assert handoff_body["status"] == "CLOSED"
    handoff = handoff_body["packaging_readiness_handoff"]
    assert handoff["handoff_version"] == 2
    assert handoff["is_current"] is True
    assert handoff["readiness_status"] in {"READY", "READY_WITH_WAIVERS"}

    with SessionLocal() as db:
        v1 = db.scalar(
            select(PackagingReadinessHandoff).where(
                PackagingReadinessHandoff.fermentation_session_id == uuid.UUID(session_id),
                PackagingReadinessHandoff.handoff_version == 1,
            )
        )
        assert v1 is not None
        assert v1.is_current is False
        assert v1.readiness_status == "INVALIDATED"


def test_ac047_adv012_section25_deny_matrix_closed_and_aborted(started_fermentation):
    """P4-AC-047 / P4-ADV-012: §25 DENY cells for CLOSED and ABORTED surfaces that exist."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    assert _close(client, session_id).status_code == 200

    deny_commands = [
        (
            "abort",
            {
                "operation_id": str(uuid.uuid4()),
                "expected_revision": _revision(client, session_id),
                "reason": "Illegal abort after close must be denied by terminal matrix",
            },
        ),
        (
            "pause",
            {
                "operation_id": str(uuid.uuid4()),
                "expected_revision": _revision(client, session_id),
            },
        ),
        (
            "complete-fermentation",
            {
                "operation_id": str(uuid.uuid4()),
                "expected_revision": _revision(client, session_id),
            },
        ),
        (
            "start-conditioning",
            {
                "operation_id": str(uuid.uuid4()),
                "expected_revision": _revision(client, session_id),
            },
        ),
        (
            "skip-conditioning",
            {
                "operation_id": str(uuid.uuid4()),
                "expected_revision": _revision(client, session_id),
            },
        ),
    ]
    for command, payload in deny_commands:
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/commands/{command}",
            json=payload,
        )
        assert response.status_code == 409, (command, response.text)
        assert response.json()["code"] in {
            "TERMINAL_SESSION",
            "INVALID_TRANSITION",
        }, command

    waiver = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/waivers",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
            "requirement_class": "ORIGINAL_GRAVITY_KNOWN",
            "reason": "Illegal closed-session readiness waiver must be denied",
        },
    )
    assert waiver.status_code == 409, waiver.text


def test_adv012_aborted_resume_denied(started_fermentation):
    """P4-ADV-012 ABORTED cell: resume after abort → 409 INVALID_TRANSITION."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    aborted = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/abort",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
            "reason": "Abort for §25 DENY matrix adversarial coverage path",
        },
    )
    assert aborted.status_code == 200, aborted.text
    resume = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/resume",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert resume.status_code == 409, resume.text
    assert resume.json()["code"] == "INVALID_TRANSITION"
    pause = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert pause.status_code == 409, pause.text


def test_fr074_close_vs_stale_revision(started_fermentation):
    """P4-FR-074: stale revision on Close → 409 STALE_REVISION."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    stale = _revision(client, session_id) - 1
    denied = _close(client, session_id, revision=stale)
    assert denied.status_code == 409, denied.text
    assert denied.json()["code"] == "STALE_REVISION"


def test_recovery_reread_closed_and_handoff(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    closed = _close(client, session_id)
    assert closed.status_code == 200
    # Reconstruct from durable store via a subsequent read (no Redis/browser authority).
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "CLOSED"
    assert detail.json()["closed_at"] is not None
    assert detail.json()["packaging_readiness_handoff"]["is_current"] is True


def test_slice11_serialization_regression_idempotent_close_payload(started_fermentation):
    """Slice 11 datetime serialization regression: Close result_payload must be JSON-safe."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    op = str(uuid.uuid4())
    rev = _revision(client, session_id)
    first = _close(client, session_id, operation_id=op, revision=rev)
    assert first.status_code == 200, first.text
    second = _close(client, session_id, operation_id=op, revision=rev)
    assert second.status_code == 200, second.text


@pytest.mark.skipif(os.getenv("TEST_USE_POSTGRES") != "1", reason="PostgreSQL concurrency")
def test_fr074_concurrent_close_one_winner(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    rev = _revision(client, session_id)
    barrier = threading.Barrier(2)
    results: list[int] = []
    lock = threading.Lock()

    def _race():
        barrier.wait()
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/commands/close",
            json={"operation_id": str(uuid.uuid4()), "expected_revision": rev},
        )
        with lock:
            results.append(response.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: _race(), range(2)))
    assert 200 in results
    assert 409 in results
