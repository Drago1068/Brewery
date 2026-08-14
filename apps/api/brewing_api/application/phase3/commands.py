from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.brew_day import (
    _aware,
    _bump,
    _stage_for_user,
    get_session,
)
from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.application.events import audit, journal
from brewing_api.application.phase3.operations import replay_or_conflict, store_success
from brewing_api.application.phase3.plan import _materialize_occurrence_requirements
from brewing_api.domain.brew_day.models import (
    BrewNote,
    BrewPitchHandoff,
    BrewReminderHistory,
    BrewStageRequirement,
    BrewTimerRevision,
)
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage, BrewTimer
from brewing_api.domain.identity.models import User
from brewing_api.domain.notifications.models import Notification
from brewing_api.platform.time import utc_now


def _require_active(session: BrewSession) -> None:
    if session.status != "ACTIVE":
        raise ConflictError("Brew session must be ACTIVE")


def _lock_revision(session: BrewSession, expected: int | None) -> None:
    if expected is not None and session.revision != expected:
        raise ConflictError(
            "Stale session revision",
            code="STALE_REVISION",
            extra={"revision": session.revision},
        )


def pause_session(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    expected_revision: int | None = None,
    operation_id: str | None = None,
) -> BrewSession:
    session = get_session(db, user, session_id)
    document = {"session_id": str(session_id), "expected_revision": expected_revision}
    replay = replay_or_conflict(
        db, user.id, "pause_session", "BrewSession", session.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewSession, replay.result_resource_id)
        if found:
            return found
    _require_active(session)
    _lock_revision(session, expected_revision)
    now = utc_now()
    session.status = "PAUSED"
    session.paused_at = now
    stage = db.scalar(
        select(BrewStage).where(
            BrewStage.brew_session_id == session.id, BrewStage.status == "ACTIVE"
        )
    )
    if stage:
        stage.status = "PAUSED"
        stage.paused_at = now
    timers = db.scalars(
        select(BrewTimer)
        .join(BrewStage, BrewStage.id == BrewTimer.brew_stage_id)
        .where(BrewStage.brew_session_id == session.id, BrewTimer.status == "RUNNING")
    ).all()
    for timer in timers:
        if timer.clock_basis == "ACTIVE_TIME":
            timer.status = "PAUSED"
            timer.paused_at = now
            timer.paused_by = "SESSION_ACTION"
    journal(db, session.id, "BREW_SESSION_PAUSED", "Brew session paused", actor_id=user.id)
    audit(db, user.id, "BREW_SESSION_PAUSED", "BrewSession", session.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "pause_session",
        "BrewSession",
        session.id,
        operation_id,
        document,
        {"id": str(session.id), "status": session.status},
        "BrewSession",
        session.id,
    )
    db.commit()
    db.refresh(session)
    return session


def resume_session(
    db: Session, user: User, session_id: uuid.UUID, expected_revision: int | None = None
) -> BrewSession:
    session = get_session(db, user, session_id)
    if session.status != "PAUSED":
        raise ConflictError("Only a paused session can be resumed")
    _lock_revision(session, expected_revision)
    now = utc_now()
    session.status = "ACTIVE"
    session.paused_at = None
    stage = db.scalar(
        select(BrewStage).where(
            BrewStage.brew_session_id == session.id, BrewStage.status == "PAUSED"
        )
    )
    if stage:
        if stage.paused_at:
            stage.accumulated_pause_seconds += int(
                (_aware(now) - _aware(stage.paused_at)).total_seconds()
            )
        stage.status = "ACTIVE"
        stage.paused_at = None
    timers = db.scalars(
        select(BrewTimer)
        .join(BrewStage, BrewStage.id == BrewTimer.brew_stage_id)
        .where(BrewStage.brew_session_id == session.id, BrewTimer.paused_by == "SESSION_ACTION")
    ).all()
    for timer in timers:
        if timer.paused_at:
            timer.accumulated_pause_seconds += int(
                (_aware(now) - _aware(timer.paused_at)).total_seconds()
            )
        timer.status = "RUNNING"
        timer.paused_at = None
        timer.paused_by = None
    journal(db, session.id, "BREW_SESSION_RESUMED", "Brew session resumed", actor_id=user.id)
    audit(db, user.id, "BREW_SESSION_RESUMED", "BrewSession", session.id)
    _bump(session)
    db.commit()
    db.refresh(session)
    return session


def abort_session(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    reason: str,
    expected_revision: int | None = None,
) -> BrewSession:
    session = get_session(db, user, session_id)
    if session.status in {"COMPLETED", "ABORTED"}:
        raise ConflictError("Terminal session cannot be aborted")
    if not reason or len(reason) < 10:
        raise DomainError("Abort requires a reason of at least 10 characters", 422)
    _lock_revision(session, expected_revision)
    now = utc_now()
    session.status = "ABORTED"
    session.aborted_at = now
    session.abort_reason = reason
    for stage in db.scalars(select(BrewStage).where(BrewStage.brew_session_id == session.id)).all():
        if stage.status not in {"COMPLETED", "SKIPPED", "ABORTED"}:
            stage.status = "ABORTED"
    for timer in db.scalars(
        select(BrewTimer)
        .join(BrewStage, BrewStage.id == BrewTimer.brew_stage_id)
        .where(BrewStage.brew_session_id == session.id)
    ).all():
        if timer.status not in {"COMPLETED", "CANCELLED"}:
            timer.status = "CANCELLED"
            timer.cancelled_at = now
            timer.cancel_reason = "SESSION_ABORTED"
    for reminder in db.scalars(
        select(Notification)
        .join(BrewStage, BrewStage.id == Notification.brew_stage_id)
        .where(BrewStage.brew_session_id == session.id)
    ).all():
        if reminder.status not in {"COMPLETED", "SKIPPED", "CANCELLED"}:
            prior = reminder.status
            reminder.status = "CANCELLED"
            db.add(
                BrewReminderHistory(
                    reminder_id=reminder.id,
                    prior_status=prior,
                    new_status="CANCELLED",
                    cause="SESSION_ABORTED",
                    actor_user_id=user.id,
                )
            )
    journal(
        db, session.id, "BREW_SESSION_ABORTED", f"Brew session aborted: {reason}", actor_id=user.id
    )
    audit(db, user.id, "BREW_SESSION_ABORTED", "BrewSession", session.id, {"reason": reason})
    _bump(session)
    db.commit()
    db.refresh(session)
    return session


def skip_stage(
    db: Session, user: User, stage_id: uuid.UUID, reason: str, expected_revision: int | None = None
) -> BrewStage:
    stage, session = _stage_for_user(db, user, stage_id)
    _require_active(session)
    _lock_revision(session, expected_revision)
    if stage.required:
        raise ConflictError("Mandatory stages cannot be skipped")
    if stage.status != "PENDING":
        raise ConflictError("Only a pending optional stage can be skipped")
    if not reason:
        raise DomainError("Skip requires a reason", 422)
    now = utc_now()
    stage.status = "SKIPPED"
    stage.skip_reason = reason
    stage.completed_at = now
    journal(
        db, session.id, "BREW_STAGE_SKIPPED", f"{stage.name} skipped", stage.id, actor_id=user.id
    )
    audit(db, user.id, "BREW_STAGE_SKIPPED", "BrewStage", stage.id, {"reason": reason})
    _bump(session)
    db.commit()
    db.refresh(stage)
    return stage


def start_stage(
    db: Session, user: User, stage_id: uuid.UUID, expected_revision: int | None = None
) -> BrewStage:
    stage, session = _stage_for_user(db, user, stage_id)
    _require_active(session)
    _lock_revision(session, expected_revision)
    active = db.scalar(
        select(BrewStage).where(
            BrewStage.brew_session_id == session.id, BrewStage.status.in_(("ACTIVE", "PAUSED"))
        )
    )
    if active:
        raise ConflictError("Another primary stage is already active")
    if stage.status != "PENDING":
        raise ConflictError("Stage cannot be started")
    now = utc_now()
    stage.status = "ACTIVE"
    stage.started_at = now
    if stage.target_duration_seconds:
        db.add(
            BrewTimer(
                brew_stage_id=stage.id,
                brew_session_id=session.id,
                name=f"{stage.name} timer",
                started_at=now,
                planned_duration_seconds=stage.target_duration_seconds,
                deadline_at=now + timedelta(seconds=stage.target_duration_seconds),
                clock_basis="WALL_CLOCK",
                timer_type="STAGE_PRIMARY",
            )
        )
    journal(
        db, session.id, "BREW_STAGE_STARTED", f"{stage.name} started", stage.id, actor_id=user.id
    )
    audit(db, user.id, "BREW_STAGE_STARTED", "BrewStage", stage.id)
    _bump(session)
    db.commit()
    db.refresh(stage)
    return stage


def complete_stage(
    db: Session, user: User, stage_id: uuid.UUID, expected_revision: int | None = None
) -> BrewStage:
    from brewing_api.application.brew_day import complete_mash

    stage, session = _stage_for_user(db, user, stage_id)
    if (stage.canonical_stage_type or stage.name) == "MASH":
        return complete_mash(db, user, stage_id)
    _require_active(session)
    _lock_revision(session, expected_revision)
    if stage.status != "ACTIVE":
        raise ConflictError("Stage is not active")
    blockers = list(
        db.scalars(
            select(BrewStageRequirement).where(
                BrewStageRequirement.stage_instance_id == stage.id,
                BrewStageRequirement.required.is_(True),
                BrewStageRequirement.status.in_(("PENDING", "DUE")),
            )
        ).all()
    )
    open_reminders = list(
        db.scalars(
            select(Notification).where(
                Notification.brew_stage_id == stage.id,
                Notification.status.in_(("DUE", "SCHEDULED", "ACKNOWLEDGED")),
                Notification.priority == "REQUIRED",
            )
        ).all()
    )
    if blockers or open_reminders:
        raise DomainError("Required measurements or actions are unsatisfied")
    now = utc_now()
    stage.status = "COMPLETED"
    stage.completed_at = now
    journal(
        db,
        session.id,
        "BREW_STAGE_COMPLETED",
        f"{stage.name} completed",
        stage.id,
        actor_id=user.id,
    )
    audit(db, user.id, "BREW_STAGE_COMPLETED", "BrewStage", stage.id)
    _bump(session)
    db.commit()
    db.refresh(stage)
    return stage


def extend_stage(
    db: Session,
    user: User,
    stage_id: uuid.UUID,
    extra_seconds: int,
    reason: str,
    operation_id: str | None = None,
) -> BrewStage:
    stage, session = _stage_for_user(db, user, stage_id)
    _require_active(session)
    if stage.status not in {"ACTIVE", "PAUSED"}:
        raise ConflictError("Only an active or paused stage can be extended")
    if extra_seconds <= 0:
        raise DomainError("Extension must be positive", 422)
    timer = db.scalar(
        select(BrewTimer).where(
            BrewTimer.brew_stage_id == stage.id, BrewTimer.timer_type == "STAGE_PRIMARY"
        )
    )
    if timer:
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
        "BREW_STAGE_EXTENDED",
        f"{stage.name} extended by {extra_seconds}s",
        stage.id,
        {"reason": reason},
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_STAGE_EXTENDED", "BrewStage", stage.id)
    _bump(session)
    db.commit()
    db.refresh(stage)
    return stage


def repeat_or_return_stage(
    db: Session,
    user: User,
    stage_id: uuid.UUID,
    kind: str,
    reason: str,
    expected_revision: int | None,
    operation_id: str | None,
) -> BrewStage:
    source, session = _stage_for_user(db, user, stage_id)
    document = {"stage_id": str(stage_id), "kind": kind, "reason": reason}
    replay = replay_or_conflict(
        db, user.id, "repeat_or_return", "BrewStage", source.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewStage, replay.result_resource_id)
        if found:
            return found
    _require_active(session)
    _lock_revision(session, expected_revision)
    if source.status != "COMPLETED":
        raise ConflictError("Repeat/return requires a completed source occurrence")
    if not reason:
        raise DomainError("Repeat/return requires a reason", 422)
    active = db.scalar(
        select(BrewStage).where(
            BrewStage.brew_session_id == session.id, BrewStage.status.in_(("ACTIVE", "PAUSED"))
        )
    )
    if active:
        raise ConflictError("Cannot repeat or return while another stage is active")
    later = [
        item
        for item in db.scalars(
            select(BrewStage).where(BrewStage.brew_session_id == session.id)
        ).all()
        if item.created_at > source.created_at and item.status in {"COMPLETED", "SKIPPED"}
    ]
    inferred = "RETURN" if later else "REPEAT"
    if kind.upper() not in {inferred, kind.upper()} and kind.upper() not in {"REPEAT", "RETURN"}:
        raise ConflictError("Repeat/return kind is not valid for the current chronology")
    matching = [
        item
        for item in db.scalars(
            select(BrewStage).where(BrewStage.brew_session_id == session.id)
        ).all()
        if item.plan_step_id == source.plan_step_id
        or (source.plan_step_id is None and item.id == source.id)
    ]
    max_occ = max((item.occurrence_number for item in matching), default=source.occurrence_number)
    now = utc_now()
    new_stage = BrewStage(
        brew_session_id=session.id,
        name=source.name,
        status="ACTIVE",
        started_at=now,
        target_duration_seconds=source.target_duration_seconds,
        target_temperature=source.target_temperature,
        temperature_unit=source.temperature_unit,
        target_ph=source.target_ph,
        ph_tolerance=source.ph_tolerance,
        target_gravity=source.target_gravity,
        gravity_tolerance=source.gravity_tolerance,
        plan_step_id=source.plan_step_id,
        canonical_stage_type=source.canonical_stage_type,
        occurrence_number=max_occ + 1,
        required=source.required,
        runtime_occurrence_kind=kind.upper(),
        runtime_source_stage_id=source.id,
        runtime_reason=reason,
    )
    db.add(new_stage)
    db.flush()
    _materialize_occurrence_requirements(
        db,
        session,
        new_stage,
        "RUNTIME_REPEAT_RULE" if kind.upper() == "REPEAT" else "CONTROLLED_RETURN_RULE",
    )
    if new_stage.target_duration_seconds:
        db.add(
            BrewTimer(
                brew_stage_id=new_stage.id,
                brew_session_id=session.id,
                name=f"{new_stage.name} timer #{new_stage.occurrence_number}",
                started_at=now,
                planned_duration_seconds=new_stage.target_duration_seconds,
                deadline_at=now + timedelta(seconds=new_stage.target_duration_seconds),
                clock_basis="WALL_CLOCK",
                timer_type="STAGE_PRIMARY",
            )
        )
    journal(
        db,
        session.id,
        "BREW_STAGE_RUNTIME_OCCURRENCE",
        f"{new_stage.name} {kind.lower()} created",
        new_stage.id,
        {"source_stage_id": str(source.id), "occurrence": new_stage.occurrence_number},
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_STAGE_RUNTIME_OCCURRENCE", "BrewStage", new_stage.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "repeat_or_return",
        "BrewStage",
        source.id,
        operation_id,
        document,
        {"id": str(new_stage.id), "status": new_stage.status},
        "BrewStage",
        new_stage.id,
    )
    db.commit()
    db.refresh(new_stage)
    return new_stage


def acknowledge_reminder(db: Session, user: User, reminder_id: uuid.UUID) -> Notification:
    row = db.execute(
        select(Notification, BrewStage, BrewSession)
        .join(BrewStage, BrewStage.id == Notification.brew_stage_id)
        .join(BrewSession, BrewSession.id == BrewStage.brew_session_id)
        .where(Notification.id == reminder_id, BrewSession.user_id == user.id)
    ).one_or_none()
    if row is None:
        raise DomainError("Reminder not found", 404)
    reminder, stage, session = row
    if reminder.status == "ACKNOWLEDGED":
        return reminder
    if reminder.status not in {"DUE", "EXPIRED"}:
        raise ConflictError("Reminder cannot be acknowledged")
    prior = reminder.status
    reminder.status = "ACKNOWLEDGED"
    reminder.acknowledged_at = utc_now()
    db.add(
        BrewReminderHistory(
            reminder_id=reminder.id,
            prior_status=prior,
            new_status="ACKNOWLEDGED",
            cause="BREWER_ACK",
            actor_user_id=user.id,
        )
    )
    journal(
        db, session.id, "BREW_REMINDER_ACKNOWLEDGED", reminder.message, stage.id, actor_id=user.id
    )
    _bump(session)
    db.commit()
    db.refresh(reminder)
    return reminder


def create_note(
    db: Session, user: User, session_id: uuid.UUID, body: str, stage_id: uuid.UUID | None = None
) -> BrewNote:
    session = get_session(db, user, session_id)
    if not body or len(body) > 4000:
        raise DomainError("Note must be 1 to 4000 characters", 422)
    if session.status in {"COMPLETED", "ABORTED"}:
        terminal = session.completed_at or session.aborted_at
        if terminal and utc_now() > _aware(terminal) + timedelta(days=7):
            raise ConflictError("Late entry window has closed", code="LATE_ENTRY_WINDOW_CLOSED")
    note = BrewNote(
        brew_session_id=session.id,
        stage_instance_id=stage_id,
        body=body,
        actor_user_id=user.id,
        post_terminal=session.status in {"COMPLETED", "ABORTED"},
    )
    db.add(note)
    db.flush()
    journal(db, session.id, "BREW_NOTE_ADDED", "Note added", stage_id, actor_id=user.id)
    audit(db, user.id, "BREW_NOTE_ADDED", "BrewNote", note.id)
    db.commit()
    db.refresh(note)
    return note


def record_pitch_handoff(
    db: Session, user: User, session_id: uuid.UUID, note: str, temperature_c=None
) -> BrewPitchHandoff:
    session = get_session(db, user, session_id)
    _require_active(session)
    if not note:
        raise DomainError("Yeast-pitch fact is required", 422)
    handoff = BrewPitchHandoff(
        brew_session_id=session.id,
        pitched_at=utc_now(),
        pitch_temperature_c=temperature_c,
        yeast_addition_note=note,
        actor_user_id=user.id,
    )
    db.add(handoff)
    journal(db, session.id, "YEAST_PITCH_RECORDED", "Yeast pitch recorded", actor_id=user.id)
    audit(db, user.id, "YEAST_PITCH_RECORDED", "BrewPitchHandoff", session.id)
    _bump(session)
    db.commit()
    db.refresh(handoff)
    return handoff


def completion_audit(db: Session, user: User, session_id: uuid.UUID) -> dict:
    session = get_session(db, user, session_id)
    requirements = list(
        db.scalars(
            select(BrewStageRequirement).where(BrewStageRequirement.brew_session_id == session.id)
        ).all()
    )
    measured = sum(
        1
        for item in requirements
        if item.requirement_class == "MEASUREMENT" and item.status in {"COMPLETED", "SATISFIED"}
    )
    waived = sum(1 for item in requirements if item.status == "WAIVED")
    missing = sum(
        1
        for item in requirements
        if item.required
        and item.requirement_class == "MEASUREMENT"
        and item.status not in {"COMPLETED", "SATISFIED", "WAIVED"}
    )
    return {
        "rule_version": "phase3-completion-audit-v1",
        "session_id": str(session.id),
        "status": session.status,
        "measured_count": measured,
        "waived_count": waived,
        "missing_count": missing,
        "measurement_completeness_excludes_waivers": True,
        "unresolved_reminders": sum(
            1
            for item in db.scalars(
                select(Notification)
                .join(BrewStage, BrewStage.id == Notification.brew_stage_id)
                .where(
                    BrewStage.brew_session_id == session.id,
                    Notification.status.in_(("DUE", "SCHEDULED", "ACKNOWLEDGED", "EXPIRED")),
                    Notification.priority == "REQUIRED",
                )
            )
        ),
        "unresolved_additions": sum(
            1
            for item in requirements
            if item.requirement_class == "ADDITION"
            and item.required
            and item.status not in {"SATISFIED", "COMPLETED", "WAIVED", "SKIPPED"}
        ),
    }
