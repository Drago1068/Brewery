from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.brew_day import _bump, get_session
from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit, journal
from brewing_api.application.phase3.operations import replay_or_conflict, store_success
from brewing_api.domain.brew_day.models import BrewStageRequirement
from brewing_api.domain.brew_sessions.models import BrewStage
from brewing_api.domain.identity.models import User


def complete_checklist(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    requirement_id: uuid.UUID,
    operation_id: str,
    expected_revision: int | None = None,
) -> BrewStageRequirement:
    session = get_session(db, user, session_id)
    document = {
        "requirement_id": str(requirement_id),
        "expected_revision": expected_revision,
    }
    replay = replay_or_conflict(
        db, user.id, "complete_checklist", "BrewSession", session.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.scalar(
            select(BrewStageRequirement).where(
                BrewStageRequirement.requirement_id == replay.result_resource_id
            )
        )
        if found:
            return found
    if session.status != "ACTIVE":
        raise ConflictError("Checklist completion requires an ACTIVE session")
    if expected_revision is not None and session.revision != expected_revision:
        raise ConflictError(
            "Stale session revision",
            code="STALE_REVISION",
            extra={"revision": session.revision},
        )
    requirement = db.scalar(
        select(BrewStageRequirement).where(
            BrewStageRequirement.requirement_id == requirement_id,
            BrewStageRequirement.brew_session_id == session.id,
        )
    )
    if requirement is None:
        raise NotFoundError("Requirement not found")
    if requirement.requirement_class != "CHECKLIST":
        raise DomainError("Only checklist requirements can use this completion route", 422)
    if requirement.status in {"SATISFIED", "COMPLETED", "WAIVED"}:
        return requirement
    stage = db.get(BrewStage, requirement.stage_instance_id)
    if stage is None or stage.status not in {"PENDING", "ACTIVE", "PAUSED"}:
        raise ConflictError("Checklist cannot be completed in the current stage state")
    key = (requirement.payload or {}).get("definition_key")
    if key == "YEAST_ADDITION_FACT":
        raise ConflictError(
            "Yeast-pitch fact is completed only through pitch handoff",
            code="CHECKLIST_REQUIRES_HANDOFF",
        )
    requirement.status = "SATISFIED"
    requirement.satisfaction_source_type = "CHECKLIST_CONFIRMATION"
    requirement.satisfaction_source_id = requirement.requirement_id
    journal(
        db,
        session.id,
        "CHECKLIST_SATISFIED",
        f"Checklist {(key or requirement.requirement_class)} confirmed",
        stage.id if stage else None,
        actor_id=user.id,
    )
    audit(db, user.id, "CHECKLIST_SATISFIED", "BrewStageRequirement", requirement.requirement_id)
    _bump(session)
    store_success(
        db,
        user.id,
        "complete_checklist",
        "BrewSession",
        session.id,
        operation_id,
        document,
        {"id": str(requirement.requirement_id), "status": requirement.status},
        "BrewStageRequirement",
        requirement.requirement_id,
        http_status=200,
    )
    db.commit()
    db.refresh(requirement)
    return requirement


def satisfy_preflight_checklists(db: Session, session_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    """Mark session-level PRE_BREW preflight checklists satisfied after READY succeeds."""
    rows = list(
        db.scalars(
            select(BrewStageRequirement).where(
                BrewStageRequirement.brew_session_id == session_id,
                BrewStageRequirement.requirement_class == "CHECKLIST",
                BrewStageRequirement.status.in_(("PENDING", "DUE")),
            )
        ).all()
    )
    for item in rows:
        key = (item.payload or {}).get("definition_key")
        if key not in {"PREFLIGHT", "SNAPSHOT_RECEIPT"}:
            continue
        item.status = "SATISFIED"
        item.satisfaction_source_type = "PREFLIGHT"
        item.satisfaction_source_id = session_id
        journal(
            db,
            session_id,
            "CHECKLIST_SATISFIED",
            f"Checklist {key} satisfied by preflight",
            item.stage_instance_id,
            actor_id=actor_id,
        )
