"""Phase 4 fermentation actions (§21.1 / P4-FR-056)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.application.events import audit
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.application.phase4.time_validation import FUTURE_SKEW, _aware, _coerce_aware
from brewing_api.domain.fermentation.constants import ACTION_SCHEMA_VERSION, ACTION_TYPES
from brewing_api.domain.fermentation.models import (
    FermentationAction,
    FermentationJournalEvent,
    FermentationSession,
)
from brewing_api.domain.identity.models import User
from brewing_api.platform.time import utc_now


@dataclass(frozen=True)
class RecordActionCommand:
    operation_id: str
    action_type: str
    occurred_at: datetime
    note: str | None = None
    stage_instance_id: uuid.UUID | None = None
    expected_revision: int | None = None
    context: dict[str, Any] | None = None


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def serialize_action(row: FermentationAction) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "fermentation_session_id": str(row.fermentation_session_id),
        "stage_instance_id": None if row.stage_instance_id is None else str(row.stage_instance_id),
        "action_type": row.action_type,
        "occurred_at": _iso(row.occurred_at),
        "recorded_at": _iso(row.recorded_at),
        "note": row.note,
        "context": row.context or {},
        "planned": row.planned,
        "late_entry": row.late_entry,
        "operation_id": row.operation_id,
        "schema_version": row.schema_version,
    }


def list_session_actions(db: Session, session_id: uuid.UUID) -> list[FermentationAction]:
    return list(
        db.scalars(
            select(FermentationAction)
            .where(FermentationAction.fermentation_session_id == session_id)
            .order_by(FermentationAction.occurred_at, FermentationAction.id)
        ).all()
    )


def _journal(
    db: Session,
    session_id: uuid.UUID,
    event_type: str,
    message: str,
    *,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
    stage_id: uuid.UUID | None = None,
    occurred_at: datetime | None = None,
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
            occurred_at=occurred_at or now,
            recorded_at=now,
            actor_user_id=actor_id,
            operation_id=operation_id,
        )
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


def record_action(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: RecordActionCommand,
) -> FermentationAction:
    get_fermentation_session(db, user, session_id)
    document = {
        "action_type": command.action_type,
        "occurred_at": command.occurred_at.isoformat(),
        "note": command.note,
        "stage_instance_id": None
        if command.stage_instance_id is None
        else str(command.stage_instance_id),
        "expected_revision": command.expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "RecordAction",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationAction, replay.result_resource_id)
        if found:
            return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    if session.status in {"CLOSED", "ABORTED"}:
        raise ConflictError(
            "New actions are prohibited after the session is terminal",
            code="TERMINAL_SESSION",
        )
    if session.status == "PAUSED":
        raise ConflictError(
            "Actions cannot be recorded while the session is paused",
            code="SESSION_PAUSED",
        )
    if command.action_type not in ACTION_TYPES:
        raise DomainError("Unsupported action type", 422, code="INVALID_ACTION_TYPE")
    if command.note is not None and len(command.note) > 4000:
        raise DomainError("Action note must be at most 4000 characters", 422)

    occurred_at = _aware(command.occurred_at)
    now = utc_now()
    if occurred_at > _coerce_aware(now) + FUTURE_SKEW:
        raise DomainError(
            "occurred_at cannot be more than five minutes in the future",
            422,
            code="TIMESTAMP_FUTURE",
        )

    action = FermentationAction(
        fermentation_session_id=session.id,
        stage_instance_id=command.stage_instance_id,
        action_type=command.action_type,
        occurred_at=occurred_at,
        recorded_at=now,
        note=command.note,
        context=command.context or {},
        planned=False,
        actor_user_id=user.id,
        operation_id=command.operation_id,
        late_entry=False,
        schema_version=ACTION_SCHEMA_VERSION,
    )
    db.add(action)
    session.revision += 1
    db.flush()
    _journal(
        db,
        session.id,
        "FERMENTATION_ACTION_RECORDED",
        f"{command.action_type} recorded",
        actor_id=user.id,
        operation_id=command.operation_id,
        stage_id=command.stage_instance_id,
        occurred_at=occurred_at,
        event_data={"action_id": str(action.id), "action_type": command.action_type},
    )
    audit(db, user.id, "FERMENTATION_ACTION_RECORDED", "FermentationAction", action.id)
    store_success(
        db,
        user.id,
        "RecordAction",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        serialize_action(action),
        "FermentationAction",
        action.id,
        http_status=201,
    )
    db.commit()
    db.refresh(action)
    return action
