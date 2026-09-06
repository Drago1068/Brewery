"""Phase 4 fermentation notes (P4-FR-064, §25 terminal window)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.application.events import audit
from brewing_api.application.phase4.journal import append_journal_event
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.application.phase4.time_validation import _coerce_aware
from brewing_api.domain.fermentation.models import FermentationNote, FermentationSession
from brewing_api.domain.identity.models import User
from brewing_api.platform.time import utc_now


def serialize_note(note: FermentationNote) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "fermentation_session_id": str(note.fermentation_session_id),
        "stage_instance_id": None
        if note.stage_instance_id is None
        else str(note.stage_instance_id),
        "body": note.body,
        "actor_user_id": str(note.actor_user_id),
        "operation_id": note.operation_id,
        "post_terminal": note.post_terminal,
        "created_at": None if note.created_at is None else note.created_at.isoformat(),
    }


def list_session_notes(db: Session, session_id: uuid.UUID) -> list[FermentationNote]:
    return list(
        db.scalars(
            select(FermentationNote)
            .where(FermentationNote.fermentation_session_id == session_id)
            .order_by(FermentationNote.created_at, FermentationNote.id)
        ).all()
    )


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


def create_note(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    body: str,
    *,
    operation_id: str,
    stage_id: uuid.UUID | None = None,
    expected_revision: int | None = None,
) -> FermentationNote:
    get_fermentation_session(db, user, session_id)
    document = {
        "session_id": str(session_id),
        "body": body,
        "stage_id": None if stage_id is None else str(stage_id),
        "expected_revision": expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "create_note",
        "FermentationSession",
        session_id,
        operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationNote, replay.result_resource_id)
        if found:
            return found

    session = _lock_session(db, user, session_id)
    if expected_revision is not None and session.revision != expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    if not body or len(body) > 4000:
        raise DomainError("Note must be 1 to 4000 characters", 422)
    if session.status in {"CLOSED", "ABORTED"}:
        terminal = session.closed_at or session.aborted_at
        if terminal is None or utc_now() > _coerce_aware(terminal) + timedelta(days=7):
            raise ConflictError("Late entry window has closed", code="LATE_ENTRY_WINDOW_CLOSED")

    note = FermentationNote(
        fermentation_session_id=session.id,
        stage_instance_id=stage_id,
        body=body,
        actor_user_id=user.id,
        operation_id=operation_id,
        post_terminal=session.status in {"CLOSED", "ABORTED"},
    )
    db.add(note)
    session.revision += 1
    db.flush()
    append_journal_event(
        db,
        session.id,
        "FERMENTATION_NOTE_ADDED",
        "Note added",
        actor_id=user.id,
        operation_id=operation_id,
        stage_id=stage_id,
        event_data={"note_id": str(note.id)},
    )
    audit(db, user.id, "FERMENTATION_NOTE_ADDED", "FermentationNote", note.id)
    store_success(
        db,
        user.id,
        "create_note",
        "FermentationSession",
        session.id,
        operation_id,
        document,
        {"id": str(note.id)},
        "FermentationNote",
        note.id,
        http_status=201,
    )
    db.commit()
    db.refresh(note)
    return note
