"""Phase 4 fermentation reminder acknowledgement and satisfaction (§20)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationReminder,
    FermentationReminderHistory,
    FermentationSession,
)
from brewing_api.domain.identity.models import User
from brewing_api.platform.time import utc_now


def _journal(
    db: Session,
    session_id: uuid.UUID,
    event_type: str,
    message: str,
    *,
    stage_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
    event_data: dict | None = None,
) -> None:
    now = utc_now()
    db.add(
        FermentationJournalEvent(
            fermentation_session_id=session_id,
            fermentation_stage_id=stage_id,
            event_type=event_type,
            message=message,
            event_data=event_data or {},
            occurred_at=now,
            recorded_at=now,
            actor_user_id=actor_id,
            operation_id=operation_id,
        )
    )


def _history(
    db: Session,
    reminder: FermentationReminder,
    *,
    prior: str,
    new: str,
    cause: str,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> None:
    db.add(
        FermentationReminderHistory(
            reminder_id=reminder.id,
            fermentation_session_id=reminder.fermentation_session_id,
            prior_status=prior,
            new_status=new,
            cause=cause,
            actor_user_id=actor_id,
            operation_id=operation_id,
        )
    )


def serialize_reminder(reminder: FermentationReminder) -> dict[str, Any]:
    def _iso(value):
        return None if value is None else value.isoformat()

    return {
        "id": str(reminder.id),
        "stage_instance_id": str(reminder.stage_instance_id),
        "reminder_type": reminder.reminder_type,
        "message": reminder.message,
        "status": reminder.status,
        "due_at": _iso(reminder.due_at),
        "acknowledged_at": _iso(reminder.acknowledged_at),
        "completed_at": _iso(reminder.completed_at),
        "expired_at": _iso(reminder.expired_at),
        "requirement_class": reminder.requirement_class,
        "priority": reminder.priority,
        "activation_ordinal": reminder.activation_ordinal,
        "satisfaction_source_type": reminder.satisfaction_source_type,
        "satisfaction_source_id": None
        if reminder.satisfaction_source_id is None
        else str(reminder.satisfaction_source_id),
        "is_satisfied": reminder.satisfaction_source_type is not None
        and reminder.status == "COMPLETED",
        "schema_version": reminder.schema_version,
    }


def project_reminders(db: Session, session_id: uuid.UUID) -> list[FermentationReminder]:
    now = utc_now()
    reminders = list(
        db.scalars(
            select(FermentationReminder).where(
                FermentationReminder.fermentation_session_id == session_id
            )
        ).all()
    )
    for reminder in reminders:
        if reminder.status == "SCHEDULED" and reminder.due_at <= now:
            prior = reminder.status
            reminder.status = "DUE"
            _history(db, reminder, prior=prior, new="DUE", cause="DUE_PROJECTION")
            _journal(
                db,
                session_id,
                "FERMENTATION_REMINDER_DUE",
                reminder.message,
                stage_id=reminder.stage_instance_id,
                event_data={"reminder_id": str(reminder.id)},
            )
    db.flush()
    return reminders


def acknowledge_reminder(
    db: Session,
    user: User,
    reminder_id: uuid.UUID,
    *,
    operation_id: str,
    expected_revision: int | None = None,
) -> FermentationReminder:
    document = {
        "command_name": "AcknowledgeReminder",
        "expected_revision": expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "AcknowledgeReminder",
        "FermentationReminder",
        reminder_id,
        operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationReminder, replay.result_resource_id)
        if found:
            return found

    locked = db.execute(
        select(FermentationSession, FermentationReminder)
        .join(
            FermentationReminder,
            FermentationReminder.fermentation_session_id == FermentationSession.id,
        )
        .where(
            FermentationReminder.id == reminder_id,
            FermentationSession.user_id == user.id,
        )
        .with_for_update()
    ).one_or_none()
    if locked is None:
        raise NotFoundError("Reminder not found")
    session, reminder = locked
    if expected_revision is not None and session.revision != expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")

    if reminder.status == "ACKNOWLEDGED":
        store_success(
            db,
            user.id,
            "AcknowledgeReminder",
            "FermentationReminder",
            reminder.id,
            operation_id,
            document,
            serialize_reminder(reminder),
            "FermentationReminder",
            reminder.id,
        )
        db.commit()
        return reminder

    if reminder.status not in {"DUE", "EXPIRED"}:
        raise ConflictError(
            "Only DUE or EXPIRED reminders can be acknowledged",
            code="INVALID_REMINDER_STATE",
        )

    prior = reminder.status
    now = utc_now()
    reminder.status = "ACKNOWLEDGED"
    reminder.acknowledged_at = now
    session.revision += 1
    _history(
        db,
        reminder,
        prior=prior,
        new="ACKNOWLEDGED",
        cause="BREWER_ACK",
        actor_id=user.id,
        operation_id=operation_id,
    )
    _journal(
        db,
        session.id,
        "FERMENTATION_REMINDER_ACKNOWLEDGED",
        f"{reminder.reminder_type} acknowledged",
        stage_id=reminder.stage_instance_id,
        actor_id=user.id,
        operation_id=operation_id,
        event_data={
            "reminder_id": str(reminder.id),
            "satisfied": False,
        },
    )
    audit(db, user.id, "FERMENTATION_REMINDER_ACKNOWLEDGED", "FermentationReminder", reminder.id)
    store_success(
        db,
        user.id,
        "AcknowledgeReminder",
        "FermentationReminder",
        reminder.id,
        operation_id,
        document,
        serialize_reminder(reminder),
        "FermentationReminder",
        reminder.id,
    )
    db.commit()
    db.refresh(reminder)
    return reminder


def satisfy_gravity_reminders(
    db: Session,
    session: FermentationSession,
    *,
    measurement_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> list[FermentationReminder]:
    """Mark gravity_reading reminders COMPLETED with measurement as satisfaction source.

    Acknowledgement alone never reaches here — only authoritative measurement evidence.
    """
    satisfied: list[FermentationReminder] = []
    reminders = list(
        db.scalars(
            select(FermentationReminder).where(
                FermentationReminder.fermentation_session_id == session.id,
                FermentationReminder.reminder_type == "gravity_reading",
                FermentationReminder.status.in_({"DUE", "ACKNOWLEDGED", "EXPIRED"}),
            )
        ).all()
    )
    now = utc_now()
    for reminder in reminders:
        prior = reminder.status
        reminder.status = "COMPLETED"
        reminder.completed_at = now
        reminder.satisfaction_source_type = "FermentationMeasurement"
        reminder.satisfaction_source_id = measurement_id
        _history(
            db,
            reminder,
            prior=prior,
            new="COMPLETED",
            cause="AUTHORITATIVE_MEASUREMENT",
            actor_id=actor_id,
            operation_id=operation_id,
        )
        _journal(
            db,
            session.id,
            "FERMENTATION_REMINDER_COMPLETED",
            f"{reminder.reminder_type} satisfied by measurement",
            stage_id=reminder.stage_instance_id,
            actor_id=actor_id,
            operation_id=operation_id,
            event_data={
                "reminder_id": str(reminder.id),
                "satisfaction_source_id": str(measurement_id),
            },
        )
        satisfied.append(reminder)
    return satisfied


def satisfy_conditioning_temperature_reminders(
    db: Session,
    session: FermentationSession,
    *,
    measurement_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> list[FermentationReminder]:
    """Satisfy conditioning_temperature_check reminders from CONDITIONING_TEMPERATURE evidence."""
    satisfied: list[FermentationReminder] = []
    reminders = list(
        db.scalars(
            select(FermentationReminder).where(
                FermentationReminder.fermentation_session_id == session.id,
                FermentationReminder.reminder_type == "conditioning_temperature_check",
                FermentationReminder.status.in_({"DUE", "ACKNOWLEDGED", "EXPIRED"}),
            )
        ).all()
    )
    now = utc_now()
    for reminder in reminders:
        prior = reminder.status
        reminder.status = "COMPLETED"
        reminder.completed_at = now
        reminder.satisfaction_source_type = "FermentationMeasurement"
        reminder.satisfaction_source_id = measurement_id
        _history(
            db,
            reminder,
            prior=prior,
            new="COMPLETED",
            cause="AUTHORITATIVE_MEASUREMENT",
            actor_id=actor_id,
            operation_id=operation_id,
        )
        _journal(
            db,
            session.id,
            "FERMENTATION_REMINDER_COMPLETED",
            f"{reminder.reminder_type} satisfied by measurement",
            stage_id=reminder.stage_instance_id,
            actor_id=actor_id,
            operation_id=operation_id,
            event_data={
                "reminder_id": str(reminder.id),
                "satisfaction_source_id": str(measurement_id),
            },
        )
        satisfied.append(reminder)
    return satisfied
