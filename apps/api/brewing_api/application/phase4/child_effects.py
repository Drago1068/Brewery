"""Lifecycle-linked timer/reminder child-row effects (P4-FR-018, §9.6, §9.8)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.domain.fermentation.constants import (
    REMINDER_SCHEMA_VERSION,
    REMINDER_UNRESOLVED,
    TIMER_NONTERMINAL,
    TIMER_SCHEMA_VERSION,
)
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationReminder,
    FermentationReminderHistory,
    FermentationSession,
    FermentationStageInstance,
    FermentationTimer,
)
from brewing_api.platform.time import utc_now

DEFAULT_FERMENTATION_DURATION_SECONDS = 14 * 24 * 60 * 60


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


def _reminder_history(
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


def create_activation_timers(
    db: Session,
    session: FermentationSession,
    stage: FermentationStageInstance,
    *,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
    duration_seconds: int = DEFAULT_FERMENTATION_DURATION_SECONDS,
) -> list[FermentationTimer]:
    now = utc_now()
    ordinal = stage.activation_ordinal or 1
    specs = (
        ("Fermentation wall-clock checkpoint", "WALL_CLOCK", "AUXILIARY"),
        ("Active fermentation elapsed", "ACTIVE_TIME", "STAGE_PRIMARY"),
    )
    created: list[FermentationTimer] = []
    for name, clock_basis, timer_type in specs:
        timer = FermentationTimer(
            fermentation_session_id=session.id,
            stage_instance_id=stage.id,
            name=name,
            status="RUNNING",
            started_at=now,
            planned_duration_seconds=duration_seconds,
            deadline_at=now + timedelta(seconds=duration_seconds),
            clock_basis=clock_basis,
            timer_type=timer_type,
            activation_ordinal=ordinal,
            schema_version=TIMER_SCHEMA_VERSION,
        )
        db.add(timer)
        db.flush()
        _journal(
            db,
            session.id,
            "FERMENTATION_TIMER_STARTED",
            f"{timer.name} started",
            stage_id=stage.id,
            actor_id=actor_id,
            operation_id=operation_id,
            event_data={
                "timer_id": str(timer.id),
                "clock_basis": timer.clock_basis,
                "activation_ordinal": ordinal,
            },
        )
        created.append(timer)
    return created


def materialize_start_children(
    db: Session,
    session: FermentationSession,
    stage: FermentationStageInstance,
    *,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
    duration_seconds: int = DEFAULT_FERMENTATION_DURATION_SECONDS,
) -> tuple[list[FermentationTimer], list[FermentationReminder]]:
    """Create start-transaction timers/reminders for ACTIVE_FERMENTATION."""
    now = utc_now()
    timers = create_activation_timers(
        db,
        session,
        stage,
        actor_id=actor_id,
        operation_id=operation_id,
        duration_seconds=duration_seconds,
    )
    reminder = FermentationReminder(
        fermentation_session_id=session.id,
        stage_instance_id=stage.id,
        reminder_type="gravity_reading",
        message="Record fermentation gravity observations until stable",
        status="DUE",
        due_at=now,
        requirement_class="FERMENTATION_GRAVITY_STABILITY",
        requirement_template_id=uuid.uuid5(
            uuid.UUID("c4e21b8a-7d0e-5f33-9a14-8b6c2d91e0aa"),
            f"phase4-plan-v1:{session.brew_session_id}:FERMENTATION_GRAVITY_STABILITY:default",
        ),
        activation_ordinal=stage.activation_ordinal or 1,
        priority="REQUIRED",
        schema_version=REMINDER_SCHEMA_VERSION,
    )
    db.add(reminder)
    db.flush()
    _reminder_history(
        db,
        reminder,
        prior="SCHEDULED",
        new="DUE",
        cause="SESSION_STARTED",
        actor_id=actor_id,
        operation_id=operation_id,
    )
    _journal(
        db,
        session.id,
        "FERMENTATION_REMINDER_DUE",
        reminder.message,
        stage_id=stage.id,
        actor_id=actor_id,
        operation_id=operation_id,
        event_data={"reminder_id": str(reminder.id)},
    )
    return timers, [reminder]


def pause_session_timers(db: Session, session: FermentationSession) -> int:
    """Pause ACTIVE_TIME timers with paused_by=SESSION_ACTION; WALL_CLOCK continues."""
    now = utc_now()
    count = 0
    for timer in db.scalars(
        select(FermentationTimer).where(
            FermentationTimer.fermentation_session_id == session.id,
            FermentationTimer.status == "RUNNING",
            FermentationTimer.clock_basis == "ACTIVE_TIME",
        )
    ).all():
        timer.status = "PAUSED"
        timer.paused_at = now
        timer.paused_by = "SESSION_ACTION"
        timer.revision += 1
        count += 1
        _journal(
            db,
            session.id,
            "FERMENTATION_TIMER_PAUSED",
            f"{timer.name} paused by session action",
            stage_id=timer.stage_instance_id,
            event_data={"timer_id": str(timer.id), "paused_by": "SESSION_ACTION"},
        )
    return count


def resume_session_timers(db: Session, session: FermentationSession) -> int:
    """Resume only timers paused by SESSION_ACTION."""
    now = utc_now()
    count = 0
    for timer in db.scalars(
        select(FermentationTimer).where(
            FermentationTimer.fermentation_session_id == session.id,
            FermentationTimer.status == "PAUSED",
            FermentationTimer.paused_by == "SESSION_ACTION",
        )
    ).all():
        if timer.paused_at is not None:
            pause_delta = now - timer.paused_at
            timer.accumulated_pause_seconds += int(pause_delta.total_seconds())
            if timer.deadline_at is not None and timer.clock_basis == "ACTIVE_TIME":
                timer.deadline_at = timer.deadline_at + pause_delta
        timer.status = "RUNNING"
        timer.paused_at = None
        timer.paused_by = None
        timer.revision += 1
        count += 1
        _journal(
            db,
            session.id,
            "FERMENTATION_TIMER_RESUMED",
            f"{timer.name} resumed after session resume",
            stage_id=timer.stage_instance_id,
            event_data={"timer_id": str(timer.id)},
        )
    return count


def abort_session_children(
    db: Session,
    session: FermentationSession,
    *,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> None:
    now = utc_now()
    for timer in db.scalars(
        select(FermentationTimer).where(
            FermentationTimer.fermentation_session_id == session.id,
            FermentationTimer.status.in_(TIMER_NONTERMINAL),
        )
    ).all():
        timer.status = "CANCELLED"
        timer.cancelled_at = now
        timer.cancel_reason = "SESSION_ABORTED"
        timer.revision += 1
        _journal(
            db,
            session.id,
            "FERMENTATION_TIMER_CANCELLED",
            f"{timer.name} cancelled on abort",
            stage_id=timer.stage_instance_id,
            actor_id=actor_id,
            operation_id=operation_id,
            event_data={"timer_id": str(timer.id), "cause": "SESSION_ABORTED"},
        )

    for reminder in db.scalars(
        select(FermentationReminder).where(
            FermentationReminder.fermentation_session_id == session.id,
            FermentationReminder.status.in_(REMINDER_UNRESOLVED),
        )
    ).all():
        prior = reminder.status
        reminder.status = "CANCELLED"
        reminder.skip_reason = "SESSION_ABORTED"
        _reminder_history(
            db,
            reminder,
            prior=prior,
            new="CANCELLED",
            cause="SESSION_ABORTED",
            actor_id=actor_id,
            operation_id=operation_id,
        )
        _journal(
            db,
            session.id,
            "FERMENTATION_REMINDER_CANCELLED",
            f"{reminder.reminder_type} cancelled on abort",
            stage_id=reminder.stage_instance_id,
            actor_id=actor_id,
            operation_id=operation_id,
            event_data={"reminder_id": str(reminder.id), "cause": "SESSION_ABORTED"},
        )


def complete_fermentation_primary_timers(
    db: Session,
    session: FermentationSession,
    *,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> None:
    now = utc_now()
    for timer in db.scalars(
        select(FermentationTimer).where(
            FermentationTimer.fermentation_session_id == session.id,
            FermentationTimer.timer_type == "STAGE_PRIMARY",
            FermentationTimer.status.in_(TIMER_NONTERMINAL),
        )
    ).all():
        timer.status = "COMPLETED"
        timer.completed_at = now
        timer.revision += 1
        _journal(
            db,
            session.id,
            "FERMENTATION_TIMER_COMPLETED",
            f"{timer.name} completed with fermentation",
            stage_id=timer.stage_instance_id,
            actor_id=actor_id,
            operation_id=operation_id,
            event_data={"timer_id": str(timer.id)},
        )


def invalidate_and_reactivate_children(
    db: Session,
    session: FermentationSession,
    stage: FermentationStageInstance,
    *,
    cause: str = "COMPLETION_INVALIDATED",
    actor_id: uuid.UUID | None = None,
) -> tuple[list[FermentationTimer], list[FermentationReminder]]:
    """§9.8: cancel prior-activation nonterminal timers; create new timer identities; reopen reminders."""
    now = utc_now()
    for timer in db.scalars(
        select(FermentationTimer).where(
            FermentationTimer.fermentation_session_id == session.id,
            FermentationTimer.stage_instance_id == stage.id,
            FermentationTimer.status.in_(TIMER_NONTERMINAL),
        )
    ).all():
        timer.status = "CANCELLED"
        timer.cancelled_at = now
        timer.cancel_reason = cause
        timer.revision += 1
        _journal(
            db,
            session.id,
            "FERMENTATION_TIMER_CANCELLED",
            f"{timer.name} cancelled for reactivation",
            stage_id=stage.id,
            actor_id=actor_id,
            event_data={"timer_id": str(timer.id), "cause": cause},
        )

    reminders: list[FermentationReminder] = []
    for reminder in db.scalars(
        select(FermentationReminder).where(
            FermentationReminder.fermentation_session_id == session.id,
            FermentationReminder.stage_instance_id == stage.id,
        )
    ).all():
        if reminder.status in {"CANCELLED", "SKIPPED"}:
            continue
        prior = reminder.status
        had_satisfaction = reminder.satisfaction_source_type is not None
        if had_satisfaction or reminder.status == "COMPLETED":
            reminder.satisfaction_source_type = None
            reminder.satisfaction_source_id = None
            reminder.completed_at = None
            reminder.status = "ACKNOWLEDGED" if reminder.acknowledged_at else "DUE"
            reminder.activation_ordinal = stage.activation_ordinal
            reminder.due_at = now
            _reminder_history(
                db,
                reminder,
                prior=prior,
                new=reminder.status,
                cause=cause,
                actor_id=actor_id,
            )
            _journal(
                db,
                session.id,
                "FERMENTATION_REMINDER_DUE",
                f"{reminder.reminder_type} reopened after invalidation",
                stage_id=stage.id,
                actor_id=actor_id,
                event_data={"reminder_id": str(reminder.id), "cause": cause},
            )
        else:
            reminder.activation_ordinal = stage.activation_ordinal
        reminders.append(reminder)

    new_timers = create_activation_timers(db, session, stage, actor_id=actor_id)
    return new_timers, reminders
