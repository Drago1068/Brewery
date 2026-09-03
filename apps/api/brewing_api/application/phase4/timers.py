"""Phase 4 fermentation timer commands and projection (§19)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.domain.fermentation.constants import TIMER_NONTERMINAL, TIMER_SCHEMA_VERSION
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationSession,
    FermentationStageInstance,
    FermentationTimer,
    FermentationTimerRevision,
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


def _timer_for_user(
    db: Session, user: User, timer_id: uuid.UUID
) -> tuple[FermentationTimer, FermentationSession]:
    row = db.execute(
        select(FermentationTimer, FermentationSession)
        .join(
            FermentationSession,
            FermentationSession.id == FermentationTimer.fermentation_session_id,
        )
        .where(FermentationTimer.id == timer_id, FermentationSession.user_id == user.id)
    ).one_or_none()
    if row is None:
        raise NotFoundError("Timer not found")
    return row


def _require_revision(timer: FermentationTimer, expected: int | None) -> None:
    if expected is not None and timer.revision != expected:
        raise ConflictError(
            "Stale timer revision",
            code="STALE_REVISION",
            extra={"revision": timer.revision},
        )


def project_timers(db: Session, session_id: uuid.UUID) -> list[FermentationTimer]:
    """Reconstruct expiry from PostgreSQL deadlines; at most one expiry event per timer."""
    now = utc_now()
    timers = list(
        db.scalars(
            select(FermentationTimer).where(
                FermentationTimer.fermentation_session_id == session_id
            )
        ).all()
    )
    for timer in timers:
        if timer.status not in {"RUNNING", "PAUSED"}:
            continue
        if timer.deadline_at is None or now < timer.deadline_at:
            continue
        if timer.expired_at is not None:
            if timer.status != "EXPIRED":
                timer.status = "EXPIRED"
            continue
        timer.status = "EXPIRED"
        timer.expired_at = now
        timer.revision += 1
        _journal(
            db,
            session_id,
            "FERMENTATION_TIMER_EXPIRED",
            f"{timer.name} expired",
            stage_id=timer.stage_instance_id,
            event_data={"timer_id": str(timer.id)},
        )
    db.flush()
    return timers


def serialize_timer(timer: FermentationTimer, *, server_now=None) -> dict[str, Any]:
    now = server_now or utc_now()
    remaining = None
    if timer.deadline_at is not None and timer.status in {"RUNNING", "PAUSED", "EXPIRED"}:
        remaining = int((timer.deadline_at - now).total_seconds())

    def _iso(value):
        return None if value is None else value.isoformat()

    return {
        "id": str(timer.id),
        "stage_instance_id": str(timer.stage_instance_id),
        "name": timer.name,
        "status": timer.status,
        "started_at": _iso(timer.started_at),
        "planned_duration_seconds": timer.planned_duration_seconds,
        "deadline_at": _iso(timer.deadline_at),
        "clock_basis": timer.clock_basis,
        "timer_type": timer.timer_type,
        "revision": timer.revision,
        "paused_by": timer.paused_by,
        "activation_ordinal": timer.activation_ordinal,
        "expired_at": _iso(timer.expired_at),
        "acknowledged_at": _iso(timer.acknowledged_at),
        "cancelled_at": _iso(timer.cancelled_at),
        "cancel_reason": timer.cancel_reason,
        "completed_at": _iso(timer.completed_at),
        "remaining_seconds": remaining,
        "schema_version": timer.schema_version,
    }


def start_auxiliary_timer(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    *,
    stage_instance_id: uuid.UUID,
    name: str,
    planned_duration_seconds: int,
    operation_id: str,
    clock_basis: str = "WALL_CLOCK",
    expected_revision: int | None = None,
) -> FermentationTimer:
    document = {
        "command_name": "StartAuxiliaryTimer",
        "stage_instance_id": str(stage_instance_id),
        "name": name,
        "planned_duration_seconds": planned_duration_seconds,
        "clock_basis": clock_basis,
        "expected_revision": expected_revision,
    }
    replay = replay_or_conflict(
        db, user.id, "StartAuxiliaryTimer", "FermentationSession", session_id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationTimer, replay.result_resource_id)
        if found:
            return found

    session = db.scalar(
        select(FermentationSession)
        .where(FermentationSession.id == session_id, FermentationSession.user_id == user.id)
        .with_for_update()
    )
    if session is None:
        raise DomainError("Fermentation session not found", 404)
    if session.status in {"CLOSED", "ABORTED"}:
        raise ConflictError("Cannot create timers on a terminal session", code="TERMINAL_SESSION")
    if expected_revision is not None and session.revision != expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    if clock_basis not in {"WALL_CLOCK", "ACTIVE_TIME"}:
        raise DomainError("Unsupported clock_basis", 422)
    if planned_duration_seconds <= 0:
        raise DomainError("planned_duration_seconds must be positive", 422)

    stage = db.get(FermentationStageInstance, stage_instance_id)
    if stage is None or stage.fermentation_session_id != session.id:
        raise NotFoundError("Stage instance not found")

    now = utc_now()
    timer = FermentationTimer(
        fermentation_session_id=session.id,
        stage_instance_id=stage.id,
        name=name,
        status="RUNNING",
        started_at=now,
        planned_duration_seconds=planned_duration_seconds,
        deadline_at=now + timedelta(seconds=planned_duration_seconds),
        clock_basis=clock_basis,
        timer_type="AUXILIARY",
        activation_ordinal=stage.activation_ordinal or 1,
        schema_version=TIMER_SCHEMA_VERSION,
    )
    db.add(timer)
    session.revision += 1
    db.flush()
    _journal(
        db,
        session.id,
        "FERMENTATION_TIMER_STARTED",
        f"{timer.name} started",
        stage_id=stage.id,
        actor_id=user.id,
        operation_id=operation_id,
        event_data={"timer_id": str(timer.id)},
    )
    audit(db, user.id, "FERMENTATION_TIMER_STARTED", "FermentationTimer", timer.id)
    store_success(
        db,
        user.id,
        "StartAuxiliaryTimer",
        "FermentationSession",
        session.id,
        operation_id,
        document,
        serialize_timer(timer),
        "FermentationTimer",
        timer.id,
        http_status=201,
    )
    db.commit()
    db.refresh(timer)
    return timer


def pause_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    *,
    operation_id: str,
    expected_revision: int | None = None,
) -> FermentationTimer:
    timer, session = _timer_for_user(db, user, timer_id)
    document = {"command_name": "PauseTimer", "expected_revision": expected_revision}
    replay = replay_or_conflict(
        db, user.id, "PauseTimer", "FermentationTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationTimer, replay.result_resource_id)
        if found:
            return found
    if session.status not in {"ACTIVE", "CONDITIONING"}:
        raise ConflictError("Session must be ACTIVE or CONDITIONING to pause a timer")
    _require_revision(timer, expected_revision)
    if timer.status != "RUNNING":
        raise ConflictError("Only a running timer can be paused", code="INVALID_TIMER_STATE")
    now = utc_now()
    timer.status = "PAUSED"
    timer.paused_at = now
    timer.paused_by = "MANUAL"
    timer.revision += 1
    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_TIMER_PAUSED",
        f"{timer.name} paused",
        stage_id=timer.stage_instance_id,
        actor_id=user.id,
        operation_id=operation_id,
        event_data={"timer_id": str(timer.id)},
    )
    audit(db, user.id, "FERMENTATION_TIMER_PAUSED", "FermentationTimer", timer.id)
    store_success(
        db,
        user.id,
        "PauseTimer",
        "FermentationTimer",
        timer.id,
        operation_id,
        document,
        serialize_timer(timer),
        "FermentationTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer


def resume_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    *,
    operation_id: str,
    expected_revision: int | None = None,
) -> FermentationTimer:
    timer, session = _timer_for_user(db, user, timer_id)
    document = {"command_name": "ResumeTimer", "expected_revision": expected_revision}
    replay = replay_or_conflict(
        db, user.id, "ResumeTimer", "FermentationTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationTimer, replay.result_resource_id)
        if found:
            return found
    if session.status not in {"ACTIVE", "CONDITIONING"}:
        raise ConflictError("Session must be ACTIVE or CONDITIONING to resume a timer")
    _require_revision(timer, expected_revision)
    if timer.status != "PAUSED":
        raise ConflictError("Only a paused timer can be resumed", code="INVALID_TIMER_STATE")
    now = utc_now()
    if timer.paused_at is not None:
        pause_delta = now - timer.paused_at
        timer.accumulated_pause_seconds += int(pause_delta.total_seconds())
        if timer.deadline_at is not None and timer.clock_basis == "ACTIVE_TIME":
            timer.deadline_at = timer.deadline_at + pause_delta
    timer.status = "RUNNING"
    timer.paused_at = None
    timer.paused_by = None
    timer.revision += 1
    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_TIMER_RESUMED",
        f"{timer.name} resumed",
        stage_id=timer.stage_instance_id,
        actor_id=user.id,
        operation_id=operation_id,
        event_data={"timer_id": str(timer.id)},
    )
    audit(db, user.id, "FERMENTATION_TIMER_RESUMED", "FermentationTimer", timer.id)
    store_success(
        db,
        user.id,
        "ResumeTimer",
        "FermentationTimer",
        timer.id,
        operation_id,
        document,
        serialize_timer(timer),
        "FermentationTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer


def complete_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    *,
    operation_id: str,
    expected_revision: int | None = None,
) -> FermentationTimer:
    timer, session = _timer_for_user(db, user, timer_id)
    document = {"command_name": "CompleteTimer", "expected_revision": expected_revision}
    replay = replay_or_conflict(
        db, user.id, "CompleteTimer", "FermentationTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationTimer, replay.result_resource_id)
        if found:
            return found
    _require_revision(timer, expected_revision)
    if timer.status not in TIMER_NONTERMINAL:
        raise ConflictError("Timer is already terminal", code="INVALID_TIMER_STATE")
    now = utc_now()
    timer.status = "COMPLETED"
    timer.completed_at = now
    timer.revision += 1
    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_TIMER_COMPLETED",
        f"{timer.name} completed",
        stage_id=timer.stage_instance_id,
        actor_id=user.id,
        operation_id=operation_id,
        event_data={"timer_id": str(timer.id)},
    )
    audit(db, user.id, "FERMENTATION_TIMER_COMPLETED", "FermentationTimer", timer.id)
    store_success(
        db,
        user.id,
        "CompleteTimer",
        "FermentationTimer",
        timer.id,
        operation_id,
        document,
        serialize_timer(timer),
        "FermentationTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer


def cancel_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    *,
    operation_id: str,
    reason: str,
    expected_revision: int | None = None,
) -> FermentationTimer:
    timer, session = _timer_for_user(db, user, timer_id)
    document = {
        "command_name": "CancelTimer",
        "reason": reason,
        "expected_revision": expected_revision,
    }
    replay = replay_or_conflict(
        db, user.id, "CancelTimer", "FermentationTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationTimer, replay.result_resource_id)
        if found:
            return found
    if not reason or not (10 <= len(reason) <= 1000):
        raise DomainError("Cancel reason must be 10 to 1000 characters", 422)
    _require_revision(timer, expected_revision)
    if timer.status not in TIMER_NONTERMINAL:
        raise ConflictError("Timer is already terminal", code="INVALID_TIMER_STATE")
    now = utc_now()
    timer.status = "CANCELLED"
    timer.cancelled_at = now
    timer.cancel_reason = reason
    timer.revision += 1
    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_TIMER_CANCELLED",
        f"{timer.name} cancelled",
        stage_id=timer.stage_instance_id,
        actor_id=user.id,
        operation_id=operation_id,
        event_data={"timer_id": str(timer.id)},
    )
    audit(db, user.id, "FERMENTATION_TIMER_CANCELLED", "FermentationTimer", timer.id)
    store_success(
        db,
        user.id,
        "CancelTimer",
        "FermentationTimer",
        timer.id,
        operation_id,
        document,
        serialize_timer(timer),
        "FermentationTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer


def acknowledge_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    *,
    operation_id: str,
) -> FermentationTimer:
    timer, session = _timer_for_user(db, user, timer_id)
    document = {"command_name": "AcknowledgeTimer"}
    replay = replay_or_conflict(
        db, user.id, "AcknowledgeTimer", "FermentationTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationTimer, replay.result_resource_id)
        if found:
            return found
    project_timers(db, session.id)
    db.refresh(timer)
    if timer.status == "RUNNING" and timer.deadline_at and utc_now() >= timer.deadline_at:
        timer.status = "EXPIRED"
        timer.expired_at = timer.expired_at or utc_now()
    if timer.status != "EXPIRED":
        raise ConflictError("Only an expired timer can be acknowledged", code="INVALID_TIMER_STATE")
    now = utc_now()
    timer.status = "ACKNOWLEDGED"
    timer.acknowledged_at = now
    timer.revision += 1
    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_TIMER_COMPLETED",
        f"{timer.name} acknowledged after expiry",
        stage_id=timer.stage_instance_id,
        actor_id=user.id,
        operation_id=operation_id,
        event_data={"timer_id": str(timer.id)},
    )
    audit(db, user.id, "FERMENTATION_TIMER_ACKNOWLEDGED", "FermentationTimer", timer.id)
    store_success(
        db,
        user.id,
        "AcknowledgeTimer",
        "FermentationTimer",
        timer.id,
        operation_id,
        document,
        serialize_timer(timer),
        "FermentationTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer


def extend_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    *,
    operation_id: str,
    extra_seconds: int,
    reason: str,
    expected_revision: int | None = None,
) -> FermentationTimer:
    timer, session = _timer_for_user(db, user, timer_id)
    document = {
        "command_name": "ExtendTimer",
        "extra_seconds": extra_seconds,
        "reason": reason,
        "expected_revision": expected_revision,
    }
    replay = replay_or_conflict(
        db, user.id, "ExtendTimer", "FermentationTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationTimer, replay.result_resource_id)
        if found:
            return found
    if not reason or not (10 <= len(reason) <= 1000):
        raise DomainError("Extend reason must be 10 to 1000 characters", 422)
    if extra_seconds <= 0:
        raise DomainError("extra_seconds must be positive", 422)
    _require_revision(timer, expected_revision)
    if timer.status not in {"RUNNING", "PAUSED", "EXPIRED"}:
        raise ConflictError("Timer cannot be extended", code="INVALID_TIMER_STATE")
    former_deadline = timer.deadline_at
    former_duration = timer.planned_duration_seconds
    timer.planned_duration_seconds += extra_seconds
    if timer.deadline_at is not None:
        timer.deadline_at = timer.deadline_at + timedelta(seconds=extra_seconds)
    if timer.status == "EXPIRED":
        timer.status = "RUNNING"
        timer.expired_at = None
    timer.revision += 1
    session.revision += 1
    db.add(
        FermentationTimerRevision(
            timer_id=timer.id,
            fermentation_session_id=session.id,
            former_deadline_at=former_deadline,
            former_duration_seconds=former_duration,
            new_deadline_at=timer.deadline_at,
            new_duration_seconds=timer.planned_duration_seconds,
            reason=reason,
            actor_user_id=user.id,
            operation_id=operation_id,
        )
    )
    _journal(
        db,
        session.id,
        "FERMENTATION_TIMER_REPLACED",
        f"{timer.name} extended",
        stage_id=timer.stage_instance_id,
        actor_id=user.id,
        operation_id=operation_id,
        event_data={"timer_id": str(timer.id), "extra_seconds": extra_seconds},
    )
    audit(db, user.id, "FERMENTATION_TIMER_EXTENDED", "FermentationTimer", timer.id)
    store_success(
        db,
        user.id,
        "ExtendTimer",
        "FermentationTimer",
        timer.id,
        operation_id,
        document,
        serialize_timer(timer),
        "FermentationTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer
