"""Phase 4 Slice 4 timers, reminders, and lifecycle child effects."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from brewing_api.domain.fermentation.models import (
    FermentationReminder,
    FermentationReminderHistory,
    FermentationSession,
    FermentationTimer,
)
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now

from phase4_fixtures import started_fermentation  # noqa: F401

pytestmark = pytest.mark.integration

_ABORT_REASON = "Batch contaminated; aborting fermentation for safety review today"
_CANCEL_REASON = "Operator cancelled auxiliary timer after confirming stage complete"


def test_start_materializes_timers_and_reminders(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert len(body["timers"]) >= 2
    clocks = {t["clock_basis"] for t in body["timers"]}
    assert "WALL_CLOCK" in clocks
    assert "ACTIVE_TIME" in clocks
    assert any(t["status"] == "RUNNING" for t in body["timers"])
    assert any(r["reminder_type"] == "gravity_reading" and r["status"] == "DUE" for r in body["reminders"])


def test_pause_resume_child_timer_effects(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    revision = started_fermentation["fermentation_revision"]
    paused = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert paused.status_code == 200, paused.text
    timers = paused.json()["timers"]
    active_time = [t for t in timers if t["clock_basis"] == "ACTIVE_TIME"]
    wall = [t for t in timers if t["clock_basis"] == "WALL_CLOCK"]
    assert all(t["status"] == "PAUSED" and t["paused_by"] == "SESSION_ACTION" for t in active_time)
    assert all(t["status"] == "RUNNING" for t in wall)

    resumed = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/resume",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": paused.json()["revision"]},
    )
    assert resumed.status_code == 200, resumed.text
    active_time = [t for t in resumed.json()["timers"] if t["clock_basis"] == "ACTIVE_TIME"]
    assert all(t["status"] == "RUNNING" and t["paused_by"] is None for t in active_time)


def test_abort_cancels_nonterminal_children(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    aborted = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/abort",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": started_fermentation["fermentation_revision"],
            "reason": _ABORT_REASON,
        },
    )
    assert aborted.status_code == 200, aborted.text
    body = aborted.json()
    assert body["status"] == "ABORTED"
    assert all(t["status"] == "CANCELLED" for t in body["timers"])
    assert all(r["status"] == "CANCELLED" for r in body["reminders"])


def test_acknowledge_does_not_satisfy_reminder(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    reminder = next(r for r in detail.json()["reminders"] if r["reminder_type"] == "gravity_reading")
    ack = client.post(
        f"/api/v1/fermentation-sessions/reminders/{reminder['id']}/acknowledge",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": detail.json()["revision"],
        },
    )
    assert ack.status_code == 200, ack.text
    body = ack.json()
    assert body["status"] == "ACKNOWLEDGED"
    assert body["is_satisfied"] is False
    assert body["satisfaction_source_type"] is None


def test_measurement_satisfies_gravity_reminder(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    reminder = next(r for r in detail.json()["reminders"] if r["reminder_type"] == "gravity_reading")
    client.post(
        f"/api/v1/fermentation-sessions/reminders/{reminder['id']}/acknowledge",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": detail.json()["revision"],
        },
    )
    observed_at = utc_now().isoformat()
    measured = client.post(
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
    assert measured.status_code == 201, measured.text
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    reminder = next(r for r in detail.json()["reminders"] if r["id"] == reminder["id"])
    assert reminder["status"] == "COMPLETED"
    assert reminder["is_satisfied"] is True
    assert reminder["satisfaction_source_type"] == "FermentationMeasurement"


def test_timer_expiry_projection_single_event(started_fermentation):
    client = started_fermentation["client"]
    session_id = uuid.UUID(started_fermentation["fermentation_session_id"])
    with SessionLocal() as db:
        timer = db.scalar(
            select(FermentationTimer).where(
                FermentationTimer.fermentation_session_id == session_id,
                FermentationTimer.clock_basis == "WALL_CLOCK",
            )
        )
        assert timer is not None
        timer.deadline_at = utc_now() - timedelta(minutes=1)
        db.commit()
        timer_id = timer.id

    first = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert first.status_code == 200
    expired = next(t for t in first.json()["timers"] if t["id"] == str(timer_id))
    assert expired["status"] == "EXPIRED"

    second = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    with SessionLocal() as db:
        from brewing_api.domain.fermentation.models import FermentationJournalEvent

        events = list(
            db.scalars(
                select(FermentationJournalEvent).where(
                    FermentationJournalEvent.fermentation_session_id == session_id,
                    FermentationJournalEvent.event_type == "FERMENTATION_TIMER_EXPIRED",
                )
            ).all()
        )
        assert len(events) == 1
    assert second.status_code == 200


def test_complete_fermentation_completes_primary_timers(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    observed_at = utc_now().isoformat()
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
    complete = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/complete-fermentation",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": revision,
            "override": True,
            "override_reason": "Owner override after visual krausen drop confirmed stable",
        },
    )
    assert complete.status_code == 200, complete.text
    primary = [t for t in complete.json()["timers"] if t["timer_type"] == "STAGE_PRIMARY"]
    assert primary
    assert all(t["status"] == "COMPLETED" for t in primary)


def test_invalidation_creates_new_timer_identities(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    observed_at = utc_now().isoformat()
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
        before_ids = {
            str(t.id)
            for t in db.scalars(
                select(FermentationTimer).where(
                    FermentationTimer.fermentation_session_id == uuid.UUID(session_id),
                    FermentationTimer.status == "RUNNING",
                )
            ).all()
        }
    complete = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/complete-fermentation",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": revision,
            "override": True,
            "override_reason": "Owner override after visual krausen drop confirmed stable",
        },
    )
    assert complete.status_code == 200, complete.text
    corrected = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{gravity.json()['id']}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": gravity.json()["id"],
            "reason": "Corrected hydrometer reading after reviewing lab notes from yesterday",
            "value": "1.030",
            "unit": "SG",
            "method": "HYDROMETER",
        },
    )
    assert corrected.status_code == 201, corrected.text
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert detail.json()["status"] == "ACTIVE"
    running = [t for t in detail.json()["timers"] if t["status"] == "RUNNING"]
    assert running
    assert all(t["id"] not in before_ids for t in running)
    assert all(t["activation_ordinal"] >= 2 for t in running)


def test_acknowledge_idempotency(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    reminder = next(r for r in detail.json()["reminders"] if r["reminder_type"] == "gravity_reading")
    op = "ack-reminder-replay-1"
    first = client.post(
        f"/api/v1/fermentation-sessions/reminders/{reminder['id']}/acknowledge",
        json={"operation_id": op, "expected_revision": detail.json()["revision"]},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/api/v1/fermentation-sessions/reminders/{reminder['id']}/acknowledge",
        json={"operation_id": op, "expected_revision": detail.json()["revision"]},
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    with SessionLocal() as db:
        history = list(
            db.scalars(
                select(FermentationReminderHistory).where(
                    FermentationReminderHistory.reminder_id == uuid.UUID(reminder["id"]),
                    FermentationReminderHistory.cause == "BREWER_ACK",
                )
            ).all()
        )
        assert len(history) == 1
