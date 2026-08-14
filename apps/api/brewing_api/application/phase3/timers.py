from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.brew_day import _aware, _bump
from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit, journal
from brewing_api.application.phase3.operations import replay_or_conflict, store_success
from brewing_api.domain.brew_day.models import BrewTimerRevision
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage, BrewTimer
from brewing_api.domain.identity.models import User
from brewing_api.platform.time import utc_now


def _timer_for_user(
    db: Session, user: User, timer_id: uuid.UUID
) -> tuple[BrewTimer, BrewStage, BrewSession]:
    row = db.execute(
        select(BrewTimer, BrewStage, BrewSession)
        .join(BrewStage, BrewStage.id == BrewTimer.brew_stage_id)
        .join(BrewSession, BrewSession.id == BrewStage.brew_session_id)
        .where(BrewTimer.id == timer_id, BrewSession.user_id == user.id)
    ).one_or_none()
    if row is None:
        raise NotFoundError("Timer not found")
    return row


def _require_revision(timer: BrewTimer, expected: int | None) -> None:
    if expected is not None and timer.revision != expected:
        raise ConflictError(
            "Stale timer revision",
            code="STALE_REVISION",
            extra={"revision": timer.revision},
        )


def pause_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    expected_revision: int | None = None,
    operation_id: str | None = None,
) -> BrewTimer:
    timer, stage, session = _timer_for_user(db, user, timer_id)
    document = {"timer_id": str(timer_id), "expected_revision": expected_revision}
    replay = replay_or_conflict(
        db, user.id, "pause_timer", "BrewTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewTimer, replay.result_resource_id)
        if found:
            return found
    if session.status != "ACTIVE":
        raise ConflictError("Brew session must be ACTIVE")
    _require_revision(timer, expected_revision)
    if timer.status != "RUNNING":
        raise ConflictError("Only a running timer can be paused")
    now = utc_now()
    timer.status = "PAUSED"
    timer.paused_at = now
    timer.paused_by = "MANUAL"
    timer.revision += 1
    journal(
        db,
        session.id,
        "BREW_TIMER_PAUSED",
        f"{timer.name} paused",
        stage.id,
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_TIMER_PAUSED", "BrewTimer", timer.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "pause_timer",
        "BrewTimer",
        timer.id,
        operation_id,
        document,
        {"id": str(timer.id), "status": timer.status},
        "BrewTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer


def resume_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    expected_revision: int | None = None,
    operation_id: str | None = None,
) -> BrewTimer:
    timer, stage, session = _timer_for_user(db, user, timer_id)
    document = {"timer_id": str(timer_id), "expected_revision": expected_revision}
    replay = replay_or_conflict(
        db, user.id, "resume_timer", "BrewTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewTimer, replay.result_resource_id)
        if found:
            return found
    if session.status != "ACTIVE":
        raise ConflictError("Brew session must be ACTIVE")
    _require_revision(timer, expected_revision)
    if timer.status != "PAUSED":
        raise ConflictError("Only a paused timer can be resumed")
    now = utc_now()
    if timer.paused_at:
        timer.accumulated_pause_seconds += int(
            (_aware(now) - _aware(timer.paused_at)).total_seconds()
        )
    timer.status = "RUNNING"
    timer.paused_at = None
    timer.paused_by = None
    timer.revision += 1
    journal(
        db,
        session.id,
        "BREW_TIMER_RESUMED",
        f"{timer.name} resumed",
        stage.id,
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_TIMER_RESUMED", "BrewTimer", timer.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "resume_timer",
        "BrewTimer",
        timer.id,
        operation_id,
        document,
        {"id": str(timer.id), "status": timer.status},
        "BrewTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer


def complete_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    expected_revision: int | None = None,
    operation_id: str | None = None,
) -> BrewTimer:
    timer, stage, session = _timer_for_user(db, user, timer_id)
    document = {"timer_id": str(timer_id), "expected_revision": expected_revision}
    replay = replay_or_conflict(
        db, user.id, "complete_timer", "BrewTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewTimer, replay.result_resource_id)
        if found:
            return found
    _require_revision(timer, expected_revision)
    if timer.status in {"COMPLETED", "CANCELLED"}:
        raise ConflictError("Timer is already terminal")
    now = utc_now()
    timer.status = "COMPLETED"
    timer.completed_at = now
    timer.revision += 1
    journal(
        db,
        session.id,
        "BREW_TIMER_COMPLETED",
        f"{timer.name} completed",
        stage.id,
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_TIMER_COMPLETED", "BrewTimer", timer.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "complete_timer",
        "BrewTimer",
        timer.id,
        operation_id,
        document,
        {"id": str(timer.id), "status": timer.status},
        "BrewTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer


def cancel_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    reason: str,
    expected_revision: int | None = None,
    operation_id: str | None = None,
) -> BrewTimer:
    timer, stage, session = _timer_for_user(db, user, timer_id)
    document = {
        "timer_id": str(timer_id),
        "reason": reason,
        "expected_revision": expected_revision,
    }
    replay = replay_or_conflict(
        db, user.id, "cancel_timer", "BrewTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewTimer, replay.result_resource_id)
        if found:
            return found
    if not reason:
        raise DomainError("Cancel requires a reason", 422)
    _require_revision(timer, expected_revision)
    if timer.status in {"COMPLETED", "CANCELLED"}:
        raise ConflictError("Timer is already terminal")
    now = utc_now()
    timer.status = "CANCELLED"
    timer.cancelled_at = now
    timer.cancel_reason = reason
    timer.revision += 1
    journal(
        db,
        session.id,
        "BREW_TIMER_CANCELLED",
        f"{timer.name} cancelled",
        stage.id,
        {"reason": reason},
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_TIMER_CANCELLED", "BrewTimer", timer.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "cancel_timer",
        "BrewTimer",
        timer.id,
        operation_id,
        document,
        {"id": str(timer.id), "status": timer.status},
        "BrewTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer


def acknowledge_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    operation_id: str | None = None,
) -> BrewTimer:
    timer, stage, session = _timer_for_user(db, user, timer_id)
    document = {"timer_id": str(timer_id)}
    replay = replay_or_conflict(
        db, user.id, "acknowledge_timer", "BrewTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewTimer, replay.result_resource_id)
        if found:
            return found
    if timer.status not in {"EXPIRED", "RUNNING"}:
        raise ConflictError("Timer cannot be acknowledged")
    now = utc_now()
    if timer.status == "RUNNING" and timer.deadline_at:
        if now >= _aware(timer.deadline_at):
            timer.status = "EXPIRED"
            timer.expired_at = timer.deadline_at
    if timer.status != "EXPIRED":
        raise ConflictError("Only an expired timer can be acknowledged")
    timer.status = "ACKNOWLEDGED"
    timer.acknowledged_at = now
    timer.revision += 1
    journal(
        db,
        session.id,
        "BREW_TIMER_ACKNOWLEDGED",
        f"{timer.name} expiry acknowledged",
        stage.id,
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_TIMER_ACKNOWLEDGED", "BrewTimer", timer.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "acknowledge_timer",
        "BrewTimer",
        timer.id,
        operation_id,
        document,
        {"id": str(timer.id), "status": timer.status},
        "BrewTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer


def replace_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    reason: str,
    planned_duration_seconds: int,
    operation_id: str | None = None,
) -> BrewTimer:
    original, stage, session = _timer_for_user(db, user, timer_id)
    document = {
        "timer_id": str(timer_id),
        "reason": reason,
        "planned_duration_seconds": planned_duration_seconds,
    }
    replay = replay_or_conflict(
        db, user.id, "replace_timer", "BrewTimer", original.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewTimer, replay.result_resource_id)
        if found:
            return found
    if session.status != "ACTIVE":
        raise ConflictError("Brew session must be ACTIVE")
    if not reason or len(reason) < 10:
        raise DomainError("Replacement requires a reason of at least 10 characters", 422)
    if planned_duration_seconds <= 0:
        raise DomainError("Replacement duration must be positive", 422)
    if original.status == "CANCELLED":
        raise ConflictError("Timer has already been replaced or cancelled")
    now = utc_now()
    original.status = "CANCELLED"
    original.cancelled_at = now
    original.cancel_reason = f"REPLACED: {reason}"
    original.revision += 1
    replacement = BrewTimer(
        brew_stage_id=stage.id,
        brew_session_id=session.id,
        name=f"{original.name} replacement {uuid.uuid4().hex[:8]}",
        started_at=now,
        planned_duration_seconds=planned_duration_seconds,
        deadline_at=now + timedelta(seconds=planned_duration_seconds),
        clock_basis=original.clock_basis,
        timer_type=original.timer_type,
        replaces_timer_id=original.id,
        addition_requirement_id=original.addition_requirement_id,
        continues_after_stage=original.continues_after_stage,
    )
    db.add(replacement)
    db.flush()
    journal(
        db,
        session.id,
        "BREW_TIMER_REPLACED",
        f"{original.name} replaced",
        stage.id,
        {
            "replaced_timer_id": str(original.id),
            "replacement_timer_id": str(replacement.id),
            "reason": reason,
        },
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_TIMER_REPLACED", "BrewTimer", replacement.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "replace_timer",
        "BrewTimer",
        original.id,
        operation_id,
        document,
        {"id": str(replacement.id), "status": replacement.status},
        "BrewTimer",
        replacement.id,
    )
    db.commit()
    db.refresh(replacement)
    return replacement


def extend_timer(
    db: Session,
    user: User,
    timer_id: uuid.UUID,
    extra_seconds: int,
    reason: str,
    operation_id: str | None = None,
) -> BrewTimer:
    timer, stage, session = _timer_for_user(db, user, timer_id)
    document = {
        "timer_id": str(timer_id),
        "extra_seconds": extra_seconds,
        "reason": reason,
    }
    replay = replay_or_conflict(
        db, user.id, "extend_timer", "BrewTimer", timer.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewTimer, replay.result_resource_id)
        if found:
            return found
    if extra_seconds <= 0:
        raise DomainError("Extension must be positive", 422)
    if not reason:
        raise DomainError("Extension requires a reason", 422)
    former_deadline = timer.deadline_at
    former_duration = timer.planned_duration_seconds
    timer.planned_duration_seconds += extra_seconds
    if timer.deadline_at:
        timer.deadline_at = timer.deadline_at + timedelta(seconds=extra_seconds)
    timer.revision += 1
    db.add(
        BrewTimerRevision(
            timer_id=timer.id,
            brew_session_id=session.id,
            former_deadline_at=former_deadline,
            former_duration_seconds=former_duration,
            new_deadline_at=timer.deadline_at,
            new_duration_seconds=timer.planned_duration_seconds,
            reason=reason,
            actor_user_id=user.id,
            operation_id=operation_id,
        )
    )
    journal(
        db,
        session.id,
        "BREW_TIMER_EXTENDED",
        f"{timer.name} extended by {extra_seconds}s",
        stage.id,
        {"reason": reason},
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_TIMER_EXTENDED", "BrewTimer", timer.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "extend_timer",
        "BrewTimer",
        timer.id,
        operation_id,
        document,
        {"id": str(timer.id), "status": timer.status},
        "BrewTimer",
        timer.id,
    )
    db.commit()
    db.refresh(timer)
    return timer
