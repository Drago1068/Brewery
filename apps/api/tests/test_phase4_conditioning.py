"""Phase 4 Slice 5 conditioning lifecycle and fermentation handoff."""
# ruff: noqa: F811 - test parameters intentionally shadow the fixture import

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from phase4_fixtures import started_fermentation  # noqa: F401
from phase4_lifecycle_helpers import (
    backdate_conditioning_first_started,
    complete_conditioning,
    complete_fermentation,
    reach_fermentation_complete,
    record_stable_gravities,
    set_plan_conditioning,
    skip_conditioning,
    start_conditioning,
)
from sqlalchemy import func, select

from brewing_api.domain.fermentation.models import (
    FermentationCompletionAssessment,
    FermentationJournalEvent,
    FermentationSession,
    FermentationStageInstance,
    FermentationTimer,
)
from brewing_api.platform.database import SessionLocal

pytestmark = pytest.mark.integration

_CORRECTION_REASON = "Corrected hydrometer reading after reviewing lab notes from yesterday"
_OVERRIDE_REASON = "Owner override for conditioning completion acceptance test path"


def test_skip_conditioning_when_not_required(started_fermentation):
    """P4-AC-014 / P4-FR-023 / P4-FR-047."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    payload = reach_fermentation_complete(client, started_fermentation)
    response = skip_conditioning(client, session_id=session_id, revision=payload["revision"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "CONDITIONING_COMPLETE"
    assert body["conditioning_skipped"] is True
    assert body["conditioning_started_at"] is None
    assert body["conditioning_completed_at"] is None
    assert body["conditioning_assessment"]["outcome"] == "CONDITIONING_NOT_REQUIRED"
    with SessionLocal() as db:
        stages = list(
            db.scalars(
                select(FermentationStageInstance).where(
                    FermentationStageInstance.fermentation_session_id == uuid.UUID(session_id),
                    FermentationStageInstance.canonical_stage_type == "CONDITIONING",
                )
            ).all()
        )
        assert stages == []


def test_skip_denied_when_conditioning_required(started_fermentation):
    """P4-AC-015."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id, conditioning_required=True)
    payload = reach_fermentation_complete(client, started_fermentation)
    response = skip_conditioning(client, session_id=session_id, revision=payload["revision"])
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "CONDITIONING_REQUIRED"


def test_start_conditioning_handoff_and_timers(started_fermentation):
    """P4-FR-019 handoff; timers/reminders P4-FR-018."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id)
    payload = reach_fermentation_complete(client, started_fermentation)
    ferm_assessment_id = payload["completion_assessment"]["id"]
    response = start_conditioning(client, session_id=session_id, revision=payload["revision"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "CONDITIONING"
    assert body["conditioning_mode"] == "COLD_CONDITIONING"
    assert body["conditioning_first_started_at"] is not None
    assert body["conditioning_skipped"] is False
    conditioning_stages = [s for s in body["stages"] if s["canonical_stage_type"] == "CONDITIONING"]
    assert len(conditioning_stages) == 1
    assert conditioning_stages[0]["activation_ordinal"] == 1
    assert any(
        t["timer_type"] == "STAGE_PRIMARY"
        for t in body["timers"]
        if "conditioning" in t["name"].lower()
    )
    assert any(r["reminder_type"] == "conditioning_temperature_check" for r in body["reminders"])
    with SessionLocal() as db:
        events = list(
            db.scalars(
                select(FermentationJournalEvent).where(
                    FermentationJournalEvent.fermentation_session_id == uuid.UUID(session_id),
                    FermentationJournalEvent.event_type == "FERMENTATION_STAGE_ENTERED",
                )
            ).all()
        )
        assert any(
            e.event_data.get("fermentation_assessment_id") == ferm_assessment_id for e in events
        )


def test_start_denied_when_conditioning_not_required(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    payload = reach_fermentation_complete(client, started_fermentation)
    response = start_conditioning(client, session_id=session_id, revision=payload["revision"])
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "CONDITIONING_NOT_REQUIRED"


def test_stale_revision_and_duplicate_start(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id)
    payload = reach_fermentation_complete(client, started_fermentation)
    op = str(uuid.uuid4())
    first = start_conditioning(
        client, session_id=session_id, revision=payload["revision"], operation_id=op
    )
    assert first.status_code == 200, first.text
    stale = start_conditioning(client, session_id=session_id, revision=payload["revision"])
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] in {"STALE_REVISION", "INVALID_TRANSITION"}
    replay = start_conditioning(
        client, session_id=session_id, revision=payload["revision"], operation_id=op
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "CONDITIONING"
    assert replay.json()["revision"] == first.json()["revision"]


def test_complete_conditioning_ineligible_missing_temperature(started_fermentation):
    """P4-AC-053."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(
        session_id=session_id,
        conditioning_duration_minutes=1,
        conditioning_temperature_c="2.0",
    )
    payload = reach_fermentation_complete(client, started_fermentation)
    started = start_conditioning(client, session_id=session_id, revision=payload["revision"])
    assert started.status_code == 200, started.text
    backdate_conditioning_first_started(session_id=session_id, minutes_ago=5)
    response = complete_conditioning(
        client, session_id=session_id, revision=started.json()["revision"]
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "COMPLETION_INELIGIBLE"
    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        assessment = db.scalar(
            select(FermentationCompletionAssessment).where(
                FermentationCompletionAssessment.fermentation_session_id == session.id,
                FermentationCompletionAssessment.assessment_kind == "CONDITIONING",
                FermentationCompletionAssessment.is_current.is_(True),
            )
        )
        assert session.status == "CONDITIONING"
        assert assessment is not None
        assert assessment.outcome == "INSUFFICIENT_EVIDENCE"


def test_complete_conditioning_success_with_temperature(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(
        session_id=session_id,
        conditioning_duration_minutes=1,
        conditioning_temperature_c="2.0",
    )
    payload = reach_fermentation_complete(client, started_fermentation)
    started = start_conditioning(client, session_id=session_id, revision=payload["revision"])
    assert started.status_code == 200, started.text
    stage_id = next(
        s["id"] for s in started.json()["stages"] if s["canonical_stage_type"] == "CONDITIONING"
    )
    backdate_conditioning_first_started(session_id=session_id, minutes_ago=5)
    temp = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "CONDITIONING_TEMPERATURE",
            "value": "2.0",
            "unit": "degC",
            "observed_at": datetime.now(UTC).isoformat(),
            "stage_instance_id": stage_id,
            "method": "PROBE",
            "expected_revision": started.json()["revision"],
        },
    )
    assert temp.status_code == 201, temp.text
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    rem = next(
        r
        for r in detail.json()["reminders"]
        if r["reminder_type"] == "conditioning_temperature_check"
    )
    assert rem["status"] == "COMPLETED"
    response = complete_conditioning(
        client, session_id=session_id, revision=detail.json()["revision"]
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "CONDITIONING_COMPLETE"
    assert body["conditioning_assessment"]["outcome"] == "COMPLETION_CONFIRMED"
    assert body["conditioning_current_completed_at"] is not None


def test_complete_conditioning_override(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id)
    payload = reach_fermentation_complete(client, started_fermentation)
    started = start_conditioning(client, session_id=session_id, revision=payload["revision"])
    response = complete_conditioning(
        client,
        session_id=session_id,
        revision=started.json()["revision"],
        override=True,
        override_reason=_OVERRIDE_REASON,
    )
    assert response.status_code == 200, response.text
    assert response.json()["conditioning_assessment"]["outcome"] == "COMPLETION_OVERRIDDEN"


def test_post_handoff_fermentation_invalidation_reuses_conditioning(started_fermentation):
    """P4-AC-060 / P4-ADV-036 / POST_HANDOFF_PREDECESSOR_INVALIDATION."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id)
    payload = reach_fermentation_complete(client, started_fermentation)
    started = start_conditioning(client, session_id=session_id, revision=payload["revision"])
    assert started.status_code == 200, started.text
    stage_id = next(
        s["id"] for s in started.json()["stages"] if s["canonical_stage_type"] == "CONDITIONING"
    )
    with SessionLocal() as db:
        timers_before = db.scalar(
            select(func.count())
            .select_from(FermentationTimer)
            .where(
                FermentationTimer.fermentation_session_id == uuid.UUID(session_id),
                FermentationTimer.stage_instance_id == uuid.UUID(stage_id),
                FermentationTimer.status == "RUNNING",
            )
        )
        assert timers_before >= 1

    gravity = next(
        m for m in started.json()["measurements"] if m["measurement_type"] == "FERMENTATION_GRAVITY"
    )
    correction = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{gravity['id']}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": gravity["id"],
            "reason": _CORRECTION_REASON,
            "value": "1.025",
            "unit": "SG",
            "observed_at": datetime.now(UTC).isoformat(),
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "expected_revision": started.json()["revision"],
        },
    )
    assert correction.status_code == 201, correction.text
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert detail.json()["status"] == "ACTIVE"
    with SessionLocal() as db:
        stage = db.get(FermentationStageInstance, uuid.UUID(stage_id))
        assert stage.status == "INVALIDATED"
        running = db.scalar(
            select(func.count())
            .select_from(FermentationTimer)
            .where(
                FermentationTimer.stage_instance_id == uuid.UUID(stage_id),
                FermentationTimer.status.in_(("RUNNING", "PAUSED", "PENDING", "EXPIRED")),
            )
        )
        assert running == 0

    record_stable_gravities(
        client,
        session_id=session_id,
        stage_id=started_fermentation["active_stage_id"],
        values=("1.021", "1.020", "1.019"),
    )
    with SessionLocal() as db:
        revision = db.get(FermentationSession, uuid.UUID(session_id)).revision
    completed = complete_fermentation(
        client,
        session_id=session_id,
        revision=revision,
        override=True,
        override_reason=_OVERRIDE_REASON,
    )
    assert completed.status_code == 200, completed.text
    restarted = start_conditioning(
        client, session_id=session_id, revision=completed.json()["revision"]
    )
    assert restarted.status_code == 200, restarted.text
    stages = [s for s in restarted.json()["stages"] if s["canonical_stage_type"] == "CONDITIONING"]
    assert len(stages) == 1
    assert stages[0]["id"] == stage_id
    assert stages[0]["activation_ordinal"] == 2


def test_invalid_transition_while_conditioning(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id)
    payload = reach_fermentation_complete(client, started_fermentation)
    started = start_conditioning(client, session_id=session_id, revision=payload["revision"])
    skip = skip_conditioning(client, session_id=session_id, revision=started.json()["revision"])
    assert skip.status_code == 409
    assert skip.json()["code"] == "INVALID_TRANSITION"


def test_pause_resume_preserves_conditioning_origin(started_fermentation):
    """P4-AC-013."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id)
    payload = reach_fermentation_complete(client, started_fermentation)
    started = start_conditioning(client, session_id=session_id, revision=payload["revision"])
    pause = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": started.json()["revision"],
        },
    )
    assert pause.status_code == 200, pause.text
    assert pause.json()["status"] == "PAUSED"
    assert pause.json()["pause_origin_state"] == "CONDITIONING"
    resume = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/resume",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": pause.json()["revision"],
        },
    )
    assert resume.status_code == 200, resume.text
    assert resume.json()["status"] == "CONDITIONING"


def test_recovery_after_restart_reads_conditioning_state(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    set_plan_conditioning(session_id=session_id)
    payload = reach_fermentation_complete(client, started_fermentation)
    started = start_conditioning(client, session_id=session_id, revision=payload["revision"])
    assert started.status_code == 200
    refreshed = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "CONDITIONING"
    assert refreshed.json()["revision"] == started.json()["revision"]
    assert (
        refreshed.json()["conditioning_first_started_at"]
        == started.json()["conditioning_first_started_at"]
    )
