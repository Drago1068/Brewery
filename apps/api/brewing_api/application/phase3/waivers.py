from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.brew_day import _bump, get_session
from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit, journal
from brewing_api.application.phase3.operations import replay_or_conflict, store_success
from brewing_api.domain.brew_day.models import (
    BrewReminderHistory,
    BrewStageRequirement,
    BrewWaiver,
)
from brewing_api.domain.brew_sessions.models import BrewStage
from brewing_api.domain.identity.models import User
from brewing_api.domain.notifications.models import Notification

NEVER_WAIVABLE = {
    "YEAST_ADDITION_FACT",
    "OWNERSHIP",
    "PREFLIGHT",
}


def create_waiver(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    requirement_id: uuid.UUID,
    reason: str,
    operation_id: str,
    expected_revision: int | None = None,
) -> BrewWaiver:
    session = get_session(db, user, session_id)
    document = {
        "requirement_id": str(requirement_id),
        "reason": reason,
        "expected_revision": expected_revision,
    }
    replay = replay_or_conflict(
        db, user.id, "create_waiver", "BrewSession", session.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewWaiver, replay.result_resource_id)
        if found:
            return found
    if not operation_id:
        raise DomainError("Waiver requires an operation_id", 422)
    if session.status != "ACTIVE":
        raise ConflictError("Waivers are allowed only while the session is ACTIVE")
    if expected_revision is not None and session.revision != expected_revision:
        raise ConflictError(
            "Stale session revision",
            code="STALE_REVISION",
            extra={"revision": session.revision},
        )
    if not reason or not (10 <= len(reason) <= 1000):
        raise DomainError("Waiver reason must be 10 to 1000 characters", 422)
    requirement = db.scalar(
        select(BrewStageRequirement).where(
            BrewStageRequirement.requirement_id == requirement_id,
            BrewStageRequirement.brew_session_id == session.id,
        )
    )
    if requirement is None:
        raise NotFoundError("Requirement not found")
    stage = db.get(BrewStage, requirement.stage_instance_id)
    if stage is None or stage.status not in {"PENDING", "ACTIVE", "PAUSED"}:
        raise ConflictError("Waiver is not allowed in the current stage state")
    key = (requirement.payload or {}).get("definition_key") or requirement.requirement_class
    if not requirement.waivable or key in NEVER_WAIVABLE:
        raise ConflictError("This requirement cannot be waived", code="WAIVER_PROHIBITED")
    if requirement.satisfaction_source_id and requirement.status in {"SATISFIED", "COMPLETED"}:
        raise ConflictError("Requirement already has authoritative satisfaction")
    existing = db.scalar(
        select(BrewWaiver).where(
            BrewWaiver.requirement_id == requirement.requirement_id,
            BrewWaiver.status == "ACTIVE",
        )
    )
    if existing:
        raise ConflictError("An active waiver already exists for this requirement")
    waiver = BrewWaiver(
        brew_session_id=session.id,
        stage_instance_id=stage.id,
        requirement_id=requirement.requirement_id,
        requirement_kind=requirement.requirement_class,
        status="ACTIVE",
        reason=reason,
        actor_user_id=user.id,
        operation_id=operation_id,
    )
    db.add(waiver)
    db.flush()
    requirement.status = "WAIVED"
    requirement.satisfaction_source_type = "Waiver"
    requirement.satisfaction_source_id = waiver.id
    reminder = db.scalar(
        select(Notification).where(Notification.requirement_id == requirement.requirement_id)
    )
    if reminder and reminder.status not in {"COMPLETED", "CANCELLED"}:
        prior = reminder.status
        reminder.status = "SKIPPED"
        reminder.resolution_source_type = "Waiver"
        reminder.resolution_source_id = waiver.id
        db.add(
            BrewReminderHistory(
                reminder_id=reminder.id,
                prior_status=prior,
                new_status="SKIPPED",
                cause="REQUIREMENT_WAIVED",
                actor_user_id=user.id,
                operation_id=operation_id,
            )
        )
    journal(
        db,
        session.id,
        "BREW_REQUIREMENT_WAIVED",
        f"Requirement waived: {reason}",
        stage.id,
        {"waiver_id": str(waiver.id), "requirement_id": str(requirement.requirement_id)},
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_REQUIREMENT_WAIVED", "BrewWaiver", waiver.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "create_waiver",
        "BrewSession",
        session.id,
        operation_id,
        document,
        {"id": str(waiver.id), "status": waiver.status},
        "BrewWaiver",
        waiver.id,
        terminal=False,
    )
    db.commit()
    db.refresh(waiver)
    return waiver
