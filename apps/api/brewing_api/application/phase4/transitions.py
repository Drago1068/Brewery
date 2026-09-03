"""Pause, resume, and abort session commands (§9.4)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.application.events import audit
from brewing_api.application.phase4.child_effects import (
    abort_session_children,
    pause_session_timers,
    resume_session_timers,
)
from brewing_api.application.phase4.completion import _invalidate_current_assessments, _invalidate_current_handoff
from brewing_api.application.phase4.lifecycle import assert_command_allowed
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationSession,
    FermentationStageInstance,
)
from brewing_api.domain.identity.models import User
from brewing_api.platform.time import utc_now


@dataclass(frozen=True)
class SessionCommand:
    operation_id: str
    expected_revision: int | None = None
    reason: str | None = None


def _lock_session(db: Session, user: User, session_id: uuid.UUID) -> FermentationSession:
    session = db.scalar(
        select(FermentationSession)
        .where(
            FermentationSession.id == session_id,
            FermentationSession.user_id == user.id,
        )
        .with_for_update()
    )
    if session is None:
        raise DomainError("Fermentation session not found", 404)
    return session


def _journal(
    db: Session,
    session_id: uuid.UUID,
    event_type: str,
    message: str,
    *,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
    event_data: dict | None = None,
) -> None:
    now = utc_now()
    db.add(
        FermentationJournalEvent(
            fermentation_session_id=session_id,
            event_type=event_type,
            message=message,
            event_data=event_data or {},
            occurred_at=now,
            recorded_at=now,
            actor_user_id=actor_id,
            operation_id=operation_id,
        )
    )


def _active_stage_for_pause(
    db: Session, session: FermentationSession
) -> FermentationStageInstance | None:
    if session.status == "ACTIVE":
        return db.scalar(
            select(FermentationStageInstance).where(
                FermentationStageInstance.fermentation_session_id == session.id,
                FermentationStageInstance.canonical_stage_type == "ACTIVE_FERMENTATION",
                FermentationStageInstance.status == "ACTIVE",
            )
        )
    if session.status == "CONDITIONING":
        return db.scalar(
            select(FermentationStageInstance).where(
                FermentationStageInstance.fermentation_session_id == session.id,
                FermentationStageInstance.canonical_stage_type == "CONDITIONING",
                FermentationStageInstance.status == "ACTIVE",
            )
        )
    return None


def pause_fermentation_session(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: SessionCommand,
) -> FermentationSession:
    get_fermentation_session(db, user, session_id)
    document = {
        "command_name": "PauseFermentationSession",
        "expected_revision": command.expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "PauseFermentationSession",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationSession, replay.result_resource_id)
        assert found is not None
        return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    assert_command_allowed("PauseFermentationSession", session.status)

    stage = _active_stage_for_pause(db, session)
    if stage is None:
        raise ConflictError("Invalid session transition", code="INVALID_TRANSITION")

    origin = "ACTIVE" if session.status == "ACTIVE" else "CONDITIONING"
    now = utc_now()
    session.pause_origin_state = origin
    session.status = "PAUSED"
    session.paused_stage_instance_id = stage.id
    session.paused_at = now
    stage.status = "PAUSED"
    stage.paused_at = now
    pause_session_timers(db, session)
    session.revision += 1

    _journal(
        db,
        session.id,
        "FERMENTATION_SESSION_PAUSED",
        "Fermentation session paused",
        actor_id=user.id,
        operation_id=command.operation_id,
        event_data={"pause_origin_state": session.pause_origin_state},
    )
    audit(db, user.id, "FERMENTATION_SESSION_PAUSED", "FermentationSession", session.id)
    store_success(
        db,
        user.id,
        "PauseFermentationSession",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        {"id": str(session.id), "status": session.status},
        "FermentationSession",
        session.id,
    )
    db.commit()
    db.refresh(session)
    return session


def resume_fermentation_session(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: SessionCommand,
) -> FermentationSession:
    get_fermentation_session(db, user, session_id)
    document = {
        "command_name": "ResumeFermentationSession",
        "expected_revision": command.expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "ResumeFermentationSession",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationSession, replay.result_resource_id)
        assert found is not None
        return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    assert_command_allowed("ResumeFermentationSession", session.status)
    if not session.pause_origin_state:
        raise ConflictError("Pause origin is missing", code="INVALID_TRANSITION")

    origin = session.pause_origin_state
    session.status = origin
    session.resumed_at = utc_now()
    session.paused_at = None
    if session.paused_stage_instance_id:
        stage = db.get(FermentationStageInstance, session.paused_stage_instance_id)
        if stage is not None:
            stage.status = "ACTIVE"
            stage.paused_at = None
    session.pause_origin_state = None
    session.paused_stage_instance_id = None
    resume_session_timers(db, session)
    session.revision += 1

    _journal(
        db,
        session.id,
        "FERMENTATION_SESSION_RESUMED",
        "Fermentation session resumed",
        actor_id=user.id,
        operation_id=command.operation_id,
        event_data={"restored_state": origin},
    )
    audit(db, user.id, "FERMENTATION_SESSION_RESUMED", "FermentationSession", session.id)
    store_success(
        db,
        user.id,
        "ResumeFermentationSession",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        {"id": str(session.id), "status": session.status},
        "FermentationSession",
        session.id,
    )
    db.commit()
    db.refresh(session)
    return session


def abort_fermentation_session(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: SessionCommand,
) -> FermentationSession:
    get_fermentation_session(db, user, session_id)
    document = {
        "command_name": "AbortFermentationSession",
        "expected_revision": command.expected_revision,
        "reason": command.reason,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "AbortFermentationSession",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationSession, replay.result_resource_id)
        assert found is not None
        return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    assert_command_allowed("AbortFermentationSession", session.status)
    if not command.reason or not (10 <= len(command.reason) <= 1000):
        raise DomainError("Abort reason must be 10 to 1000 characters", 422)

    now = utc_now()
    cause_id = uuid.uuid4()
    _invalidate_current_assessments(db, session, cause_id=cause_id)
    _invalidate_current_handoff(db, session, cause_id=cause_id)

    for stage in db.scalars(
        select(FermentationStageInstance).where(
            FermentationStageInstance.fermentation_session_id == session.id,
            FermentationStageInstance.status.not_in(["COMPLETED", "ABORTED"]),
        )
    ).all():
        stage.status = "ABORTED"

    session.status = "ABORTED"
    session.aborted_at = now
    session.abort_reason = command.reason
    session.pause_origin_state = None
    session.paused_stage_instance_id = None
    abort_session_children(db, session, actor_id=user.id, operation_id=command.operation_id)
    session.revision += 1

    _journal(
        db,
        session.id,
        "FERMENTATION_SESSION_ABORTED",
        "Fermentation session aborted",
        actor_id=user.id,
        operation_id=command.operation_id,
        event_data={"reason_length": len(command.reason)},
    )
    audit(db, user.id, "FERMENTATION_SESSION_ABORTED", "FermentationSession", session.id)
    store_success(
        db,
        user.id,
        "AbortFermentationSession",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        {"id": str(session.id), "status": session.status},
        "FermentationSession",
        session.id,
        terminal=True,
    )
    db.commit()
    db.refresh(session)
    return session
