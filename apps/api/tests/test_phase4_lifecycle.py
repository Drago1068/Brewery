"""Phase 4 Slice 3 lifecycle, completion, and invalidation tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from brewing_api.domain.fermentation.models import (
    FermentationCompletionAssessment,
    FermentationSession,
)
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now

from phase4_fixtures import started_fermentation  # noqa: F401
from phase4_lifecycle_helpers import complete_fermentation, record_stable_gravities

pytestmark = pytest.mark.integration

_ABORT_REASON = "Batch contaminated; aborting fermentation for safety review today"
_CORRECTION_REASON = "Corrected hydrometer reading after reviewing lab notes from yesterday"


def test_invalid_transition_from_fermentation_complete(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    record_stable_gravities(
        client,
        session_id=session_id,
        stage_id=started_fermentation["active_stage_id"],
    )
    with SessionLocal() as db:
        revision = db.get(FermentationSession, uuid.UUID(session_id)).revision
    response = complete_fermentation(client, session_id=session_id, revision=revision)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "FERMENTATION_COMPLETE"

    pause = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": response.json()["revision"]},
    )
    assert pause.status_code == 409, pause.text
    assert pause.json()["code"] == "INVALID_TRANSITION"


def test_complete_fermentation_ineligible_persists_assessment(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    revision = started_fermentation["fermentation_revision"]
    response = complete_fermentation(client, session_id=session_id, revision=revision)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "COMPLETION_INELIGIBLE"

    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        assessments = list(
            db.scalars(
                select(FermentationCompletionAssessment).where(
                    FermentationCompletionAssessment.fermentation_session_id == session.id
                )
            ).all()
        )
        assert session.status == "ACTIVE"
        assert session.revision == revision + 1
        assert len(assessments) == 1
        assert assessments[0].outcome == "INSUFFICIENT_EVIDENCE"
        assert assessments[0].is_current is True


def test_complete_fermentation_success(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    record_stable_gravities(
        client,
        session_id=session_id,
        stage_id=started_fermentation["active_stage_id"],
    )
    with SessionLocal() as db:
        revision = db.get(FermentationSession, uuid.UUID(session_id)).revision
    response = complete_fermentation(client, session_id=session_id, revision=revision)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "FERMENTATION_COMPLETE"
    assert body["completion_assessment"]["outcome"] == "COMPLETION_CONFIRMED"
    assert body["fermentation_first_completed_at"] is not None
    assert body["fermentation_current_completed_at"] is not None


def test_gravity_correction_invalidates_completion(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    observed_at = utc_now().isoformat()
    gravity = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.020",
            "unit": "SG",
            "observed_at": observed_at,
            "stage_instance_id": stage_id,
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "source": "OBSERVED",
        },
    )
    assert gravity.status_code == 201, gravity.text
    reading = gravity.json()
    with SessionLocal() as db:
        revision = db.get(FermentationSession, uuid.UUID(session_id)).revision
    complete = complete_fermentation(
        client,
        session_id=session_id,
        revision=revision,
        override=True,
        override_reason="Owner override after visual krausen drop confirmed stable",
    )
    assert complete.status_code == 200, complete.text
    assessment_id = complete.json()["completion_assessment"]["id"]

    corrected = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{reading['id']}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": reading["id"],
            "reason": _CORRECTION_REASON,
            "value": "1.030",
            "unit": "SG",
            "method": "HYDROMETER",
        },
    )
    assert corrected.status_code == 201, corrected.text
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["status"] == "ACTIVE"
    assert body["fermentation_current_completed_at"] is None
    assert body["fermentation_first_completed_at"] is not None

    with SessionLocal() as db:
        original = db.get(FermentationCompletionAssessment, uuid.UUID(assessment_id))
        current = db.scalar(
            select(FermentationCompletionAssessment).where(
                FermentationCompletionAssessment.fermentation_session_id == uuid.UUID(session_id),
                FermentationCompletionAssessment.is_current.is_(True),
            )
        )
        assert original.outcome == "COMPLETION_INVALIDATED"
        assert original.is_current is False
        assert current is None


def test_pause_resume_preserves_origin(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    revision = started_fermentation["fermentation_revision"]
    paused = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert paused.status_code == 200, paused.text
    body = paused.json()
    assert body["status"] == "PAUSED"
    assert body["pause_origin_state"] == "ACTIVE"

    resumed = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/resume",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": body["revision"]},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "ACTIVE"


def test_abort_requires_reason(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/abort",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": started_fermentation["fermentation_revision"],
            "reason": "short",
        },
    )
    assert response.status_code == 422, response.text


def test_abort_from_paused(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    revision = started_fermentation["fermentation_revision"]
    paused = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert paused.status_code == 200, paused.text
    aborted = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/abort",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": paused.json()["revision"],
            "reason": _ABORT_REASON,
        },
    )
    assert aborted.status_code == 200, aborted.text
    assert aborted.json()["status"] == "ABORTED"


def test_complete_fermentation_idempotency_replay(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    record_stable_gravities(
        client,
        session_id=session_id,
        stage_id=started_fermentation["active_stage_id"],
    )
    with SessionLocal() as db:
        revision = db.get(FermentationSession, uuid.UUID(session_id)).revision
    operation_id = "complete-ferm-replay-1"
    first = complete_fermentation(
        client, session_id=session_id, revision=revision, operation_id=operation_id
    )
    assert first.status_code == 200, first.text
    second = complete_fermentation(
        client, session_id=session_id, revision=revision, operation_id=operation_id
    )
    assert second.status_code == 200, second.text
    assert second.json()["completion_assessment"]["id"] == first.json()["completion_assessment"]["id"]


def test_complete_override_with_single_gravity(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    observed_at = datetime.now(timezone.utc).isoformat()
    gravity = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.020",
            "unit": "SG",
            "observed_at": observed_at,
            "stage_instance_id": started_fermentation["active_stage_id"],
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "source": "OBSERVED",
        },
    )
    assert gravity.status_code == 201, gravity.text
    with SessionLocal() as db:
        revision = db.get(FermentationSession, uuid.UUID(session_id)).revision
    response = complete_fermentation(
        client,
        session_id=session_id,
        revision=revision,
        override=True,
        override_reason="Owner override after visual krausen drop confirmed stable",
    )
    assert response.status_code == 200, response.text
    assert response.json()["completion_assessment"]["outcome"] == "COMPLETION_OVERRIDDEN"
