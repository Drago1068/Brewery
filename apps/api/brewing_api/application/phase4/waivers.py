"""Phase 4 fermentation waivers (§10.3 / P4-FR-059 / P4-FR-060)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.domain.brew_sessions.models import BrewSession
from brewing_api.domain.fermentation.constants import (
    CHECKPOINT_WAIVER_ALLOWED_STATUSES,
    NEVER_WAIVABLE_REQUIREMENT_KEYS,
    OG_WAIVER_ALLOWED_STATUSES,
    ORIGINAL_GRAVITY_KNOWN,
    WAIVABLE_REQUIREMENT_CLASSES,
    WAIVER_SCHEMA_VERSION,
)
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationPlanSnapshot,
    FermentationReminder,
    FermentationReminderHistory,
    FermentationSession,
    FermentationWaiver,
)
from brewing_api.domain.identity.models import User
from brewing_api.platform.time import utc_now


@dataclass(frozen=True)
class RecordWaiverCommand:
    operation_id: str
    reason: str
    requirement_id: uuid.UUID | None = None
    requirement_class: str | None = None
    expected_revision: int | None = None
    supplemental_note: str | None = None


def serialize_waiver(row: FermentationWaiver) -> dict[str, Any]:
    def _iso(value: datetime | None) -> str | None:
        return None if value is None else value.isoformat()

    return {
        "id": str(row.id),
        "requirement_class": row.requirement_class,
        "requirement_template_id": str(row.requirement_template_id),
        "reminder_id": None if row.reminder_id is None else str(row.reminder_id),
        "status": row.status,
        "reason": row.reason,
        "effect": row.effect,
        "supplemental_note": row.supplemental_note,
        "superseded_by_evidence_type": row.superseded_by_evidence_type,
        "superseded_by_evidence_id": None
        if row.superseded_by_evidence_id is None
        else str(row.superseded_by_evidence_id),
        "occurred_at": _iso(row.occurred_at),
        "recorded_at": _iso(row.recorded_at),
        "schema_version": row.schema_version,
    }


def list_session_waivers(db: Session, session_id: uuid.UUID) -> list[FermentationWaiver]:
    return list(
        db.scalars(
            select(FermentationWaiver)
            .where(FermentationWaiver.fermentation_session_id == session_id)
            .order_by(FermentationWaiver.recorded_at, FermentationWaiver.id)
        ).all()
    )


def active_waiver_for_class(
    db: Session, session_id: uuid.UUID, requirement_class: str
) -> FermentationWaiver | None:
    return db.scalar(
        select(FermentationWaiver).where(
            FermentationWaiver.fermentation_session_id == session_id,
            FermentationWaiver.requirement_class == requirement_class,
            FermentationWaiver.status == "ACTIVE",
        )
    )


def _journal(
    db: Session,
    session_id: uuid.UUID,
    event_type: str,
    message: str,
    *,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
    occurred_at: datetime | None = None,
    event_data: dict | None = None,
) -> None:
    now = utc_now()
    db.add(
        FermentationJournalEvent(
            fermentation_session_id=session_id,
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


def _normalize_key(raw: str | None) -> str:
    return (raw or "").strip().upper().replace("-", "_").replace(" ", "_")


def _plan_templates(db: Session, session: FermentationSession) -> list[dict]:
    snapshot = db.scalar(
        select(FermentationPlanSnapshot).where(
            FermentationPlanSnapshot.fermentation_session_id == session.id
        )
    )
    if snapshot is None or not isinstance(snapshot.payload, dict):
        return []
    templates = snapshot.payload.get("requirement_templates") or []
    return [item for item in templates if isinstance(item, dict)]


def _recipe_version_id(db: Session, session: FermentationSession) -> uuid.UUID:
    brew = db.get(BrewSession, session.brew_session_id)
    if brew is None:
        raise DomainError("Fermentation session not found", 404)
    return brew.recipe_version_id


def _resolve_target(
    db: Session,
    session: FermentationSession,
    command: RecordWaiverCommand,
) -> tuple[str, uuid.UUID, FermentationReminder | None, str]:
    """Return (requirement_class, template_id, reminder|None, effect)."""
    key = _normalize_key(command.requirement_class)
    if command.requirement_id is None and not key:
        raise DomainError("requirement_id or requirement_class is required", 422)

    if key and key in NEVER_WAIVABLE_REQUIREMENT_KEYS:
        raise ConflictError(
            "This requirement cannot be waived",
            code="WAIVER_PROHIBITED",
        )

    reminder: FermentationReminder | None = None
    if command.requirement_id is not None:
        reminder = db.scalar(
            select(FermentationReminder).where(
                FermentationReminder.id == command.requirement_id,
                FermentationReminder.fermentation_session_id == session.id,
            )
        )
        if reminder is not None:
            req_class = _normalize_key(reminder.requirement_class) or key
            if req_class in NEVER_WAIVABLE_REQUIREMENT_KEYS or not reminder.waivable:
                raise ConflictError(
                    "This requirement cannot be waived",
                    code="WAIVER_PROHIBITED",
                )
            if req_class not in WAIVABLE_REQUIREMENT_CLASSES:
                raise ConflictError(
                    "This requirement cannot be waived",
                    code="WAIVER_PROHIBITED",
                )
            template_id = reminder.requirement_template_id
            if template_id is None:
                raise DomainError("Reminder lacks requirement_template_id", 422)
            return req_class, template_id, reminder, "CHECKPOINT_WAIVED"

        # Treat as requirement_template_id from plan catalog.
        templates = _plan_templates(db, session)
        match = next(
            (
                item
                for item in templates
                if str(item.get("requirement_template_id")) == str(command.requirement_id)
            ),
            None,
        )
        if match is None:
            raise NotFoundError("Requirement not found")
        req_class = _normalize_key(str(match.get("requirement_class")))
        if (
            req_class in NEVER_WAIVABLE_REQUIREMENT_KEYS
            or not bool(match.get("waivable", False))
            or req_class not in WAIVABLE_REQUIREMENT_CLASSES
        ):
            raise ConflictError(
                "This requirement cannot be waived",
                code="WAIVER_PROHIBITED",
            )
        effect = (
            "READINESS_R3_WAIVED" if req_class == ORIGINAL_GRAVITY_KNOWN else "CHECKPOINT_WAIVED"
        )
        return req_class, uuid.UUID(str(match["requirement_template_id"])), None, effect

    # Class-only path (includes ADV/AC prohibited keys already handled).
    if key not in WAIVABLE_REQUIREMENT_CLASSES:
        raise ConflictError(
            "This requirement cannot be waived",
            code="WAIVER_PROHIBITED",
        )
    templates = _plan_templates(db, session)
    match = next(
        (item for item in templates if _normalize_key(str(item.get("requirement_class"))) == key),
        None,
    )
    if match is None or not bool(match.get("waivable", False)):
        raise ConflictError(
            "This requirement cannot be waived",
            code="WAIVER_PROHIBITED",
        )
    effect = "READINESS_R3_WAIVED" if key == ORIGINAL_GRAVITY_KNOWN else "CHECKPOINT_WAIVED"
    return key, uuid.UUID(str(match["requirement_template_id"])), None, effect


def _assert_lifecycle(session: FermentationSession, requirement_class: str) -> None:
    if session.status in {"CLOSED", "ABORTED"}:
        raise ConflictError(
            "Waivers are not allowed in the current session state",
            code="TERMINAL_SESSION" if session.status == "CLOSED" else "INVALID_TRANSITION",
        )
    if requirement_class == ORIGINAL_GRAVITY_KNOWN:
        if session.status not in OG_WAIVER_ALLOWED_STATUSES:
            raise ConflictError(
                "ORIGINAL_GRAVITY_KNOWN waiver is not allowed before conditioning completion",
                code="INVALID_TRANSITION",
            )
        return
    if session.status not in CHECKPOINT_WAIVER_ALLOWED_STATUSES:
        raise ConflictError(
            "Waivers are not allowed in the current session state",
            code="INVALID_TRANSITION",
        )


def record_waiver(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: RecordWaiverCommand,
) -> FermentationWaiver:
    get_fermentation_session(db, user, session_id)
    document = {
        "requirement_id": None if command.requirement_id is None else str(command.requirement_id),
        "requirement_class": command.requirement_class,
        "reason": command.reason,
        "expected_revision": command.expected_revision,
        "supplemental_note": command.supplemental_note,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "RecordWaiver",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationWaiver, replay.result_resource_id)
        if found:
            return found

    if not command.reason or not (10 <= len(command.reason) <= 1000):
        raise DomainError("Waiver reason must be 10 to 1000 characters", 422)

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")

    requirement_class, template_id, reminder, effect = _resolve_target(db, session, command)
    _assert_lifecycle(session, requirement_class)

    existing = db.scalar(
        select(FermentationWaiver).where(
            FermentationWaiver.fermentation_session_id == session.id,
            FermentationWaiver.requirement_template_id == template_id,
            FermentationWaiver.status == "ACTIVE",
        )
    )
    if existing is not None:
        raise ConflictError(
            "An active waiver already exists for this requirement",
            code="WAIVER_ALREADY_ACTIVE",
        )

    if reminder is not None and reminder.satisfaction_source_type is not None:
        raise ConflictError("Requirement already has authoritative satisfaction")

    now = utc_now()
    waiver = FermentationWaiver(
        fermentation_session_id=session.id,
        requirement_class=requirement_class,
        requirement_template_id=template_id,
        reminder_id=None if reminder is None else reminder.id,
        status="ACTIVE",
        reason=command.reason,
        effect=effect,
        supplemental_note=command.supplemental_note,
        occurred_at=now,
        recorded_at=now,
        actor_user_id=user.id,
        operation_id=command.operation_id,
        schema_version=WAIVER_SCHEMA_VERSION,
    )
    db.add(waiver)
    db.flush()

    if reminder is not None and reminder.status not in {"COMPLETED", "CANCELLED"}:
        prior = reminder.status
        reminder.status = "SKIPPED"
        reminder.skip_reason = command.reason
        reminder.resolution_source_type = "FermentationWaiver"
        reminder.resolution_source_id = waiver.id
        reminder.satisfaction_source_type = "FermentationWaiver"
        reminder.satisfaction_source_id = waiver.id
        db.add(
            FermentationReminderHistory(
                reminder_id=reminder.id,
                fermentation_session_id=session.id,
                prior_status=prior,
                new_status="SKIPPED",
                cause="REQUIREMENT_WAIVED",
                actor_user_id=user.id,
                operation_id=command.operation_id,
            )
        )
        _journal(
            db,
            session.id,
            "FERMENTATION_REMINDER_SKIPPED",
            f"{reminder.reminder_type} skipped by waiver",
            actor_id=user.id,
            operation_id=command.operation_id,
            event_data={
                "reminder_id": str(reminder.id),
                "waiver_id": str(waiver.id),
            },
        )

    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_WAIVER_RECORDED",
        f"{requirement_class} waived",
        actor_id=user.id,
        operation_id=command.operation_id,
        event_data={
            "waiver_id": str(waiver.id),
            "requirement_class": requirement_class,
            "requirement_template_id": str(template_id),
            "effect": effect,
        },
    )
    audit(db, user.id, "FERMENTATION_WAIVER_RECORDED", "FermentationWaiver", waiver.id)
    try:
        store_success(
            db,
            user.id,
            "RecordWaiver",
            "FermentationSession",
            session.id,
            command.operation_id,
            document,
            serialize_waiver(waiver),
            "FermentationWaiver",
            waiver.id,
            http_status=201,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "An active waiver already exists for this requirement",
            code="WAIVER_ALREADY_ACTIVE",
        ) from exc
    db.refresh(waiver)
    return waiver


def supersede_waiver_by_evidence(
    db: Session,
    session: FermentationSession,
    *,
    reminder: FermentationReminder,
    evidence_type: str,
    evidence_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> FermentationWaiver | None:
    """Mark ACTIVE waiver SUPERSEDED_BY_EVIDENCE when later eligible evidence arrives (§20)."""
    if reminder.satisfaction_source_type != "FermentationWaiver":
        return None
    if reminder.satisfaction_source_id is None:
        return None
    waiver = db.get(FermentationWaiver, reminder.satisfaction_source_id)
    if waiver is None or waiver.status != "ACTIVE":
        return None
    waiver.status = "SUPERSEDED_BY_EVIDENCE"
    waiver.superseded_by_evidence_type = evidence_type
    waiver.superseded_by_evidence_id = evidence_id
    _journal(
        db,
        session.id,
        "FERMENTATION_WAIVER_SUPERSEDED",
        f"{waiver.requirement_class} superseded by evidence",
        actor_id=actor_id,
        operation_id=operation_id,
        event_data={
            "waiver_id": str(waiver.id),
            "evidence_type": evidence_type,
            "evidence_id": str(evidence_id),
            "status": "SUPERSEDED_BY_EVIDENCE",
        },
    )
    return waiver
