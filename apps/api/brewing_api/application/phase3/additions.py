from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from brewing_api.application.brew_day import (
    _aware,
    _bump,
    _lock_revision,
    apply_linked_reminder_requirements,
    get_session,
)
from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit, journal
from brewing_api.application.phase3.operations import replay_or_conflict, store_success
from brewing_api.domain.brew_day.models import (
    BrewAdditionCorrection,
    BrewAdditionEvent,
    BrewReminderHistory,
    BrewStageRequirement,
    BrewWaiver,
)
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage
from brewing_api.domain.identity.models import User
from brewing_api.domain.inventory.models import InventoryTransaction
from brewing_api.domain.notifications.models import Notification
from brewing_api.platform.time import utc_now


def _requirement(
    db: Session, user: User, session_id: uuid.UUID, requirement_id: uuid.UUID
) -> tuple[BrewStageRequirement, BrewStage, BrewSession]:
    session = get_session(db, user, session_id)
    row = db.scalar(
        select(BrewStageRequirement).where(
            BrewStageRequirement.requirement_id == requirement_id,
            BrewStageRequirement.brew_session_id == session.id,
        )
    )
    if row is None:
        raise NotFoundError("Requirement not found")
    stage = db.get(BrewStage, row.stage_instance_id)
    if stage is None:
        raise NotFoundError("Stage not found")
    return row, stage, session


def _complete_addition_reminder(
    db: Session,
    stage: BrewStage,
    requirement: BrewStageRequirement,
    source_type: str,
    source_id: uuid.UUID,
    user_id: uuid.UUID,
    status: str,
) -> None:
    reminder = db.scalar(
        select(Notification).where(
            Notification.brew_stage_id == stage.id,
            Notification.requirement_id == requirement.requirement_id,
        )
    )
    if reminder is None:
        reminder = db.scalar(
            select(Notification).where(
                Notification.brew_stage_id == stage.id,
                Notification.notification_type.contains("ADDITION"),
                Notification.status.in_(("DUE", "SCHEDULED", "ACKNOWLEDGED", "EXPIRED")),
            )
        )
    if reminder is None:
        return
    prior = reminder.status
    reminder.status = status
    now = utc_now()
    if status == "COMPLETED":
        reminder.completed_at = now
        reminder.satisfaction_source_type = source_type
        reminder.satisfaction_source_id = source_id
    else:
        reminder.resolution_source_type = source_type
        reminder.resolution_source_id = source_id
    db.add(
        BrewReminderHistory(
            reminder_id=reminder.id,
            prior_status=prior,
            new_status=status,
            cause="ADDITION_EVENT" if status == "COMPLETED" else "ADDITION_SKIPPED",
            actor_user_id=user_id,
        )
    )


def execute_addition(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    requirement_id: uuid.UUID,
    quantity: Decimal,
    unit: str,
    operation_id: str | None,
    note: str | None = None,
    executed_at=None,
    late_reason: str | None = None,
    expected_revision: int | None = None,
) -> BrewAdditionEvent:
    requirement, stage, session = _requirement(db, user, session_id, requirement_id)
    document = {
        "requirement_id": str(requirement_id),
        "quantity": str(quantity),
        "unit": unit,
        "note": note,
        "expected_revision": expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "execute_addition",
        "BrewStageRequirement",
        requirement.requirement_id,
        operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewAdditionEvent, replay.result_resource_id)
        if found:
            return found
    _lock_revision(session, expected_revision)
    if requirement.requirement_class != "ADDITION":
        raise DomainError("Requirement is not an addition", 422)
    if session.status == "ABORTED":
        raise ConflictError(
            "New additions are prohibited on an aborted session",
            code="TERMINAL_SESSION_EVIDENCE_PROHIBITED",
        )
    late = False
    if stage.status == "COMPLETED":
        if not late_reason or len(late_reason) < 10:
            raise DomainError("Late addition requires a reason of at least 10 characters", 422)
        boundary = stage.completed_at or session.completed_at
        if boundary and utc_now() > _aware(boundary) + timedelta(hours=24):
            raise ConflictError("Late entry window has closed", code="LATE_ENTRY_WINDOW_CLOSED")
        late = True
    elif stage.status not in {"ACTIVE"} or session.status != "ACTIVE":
        raise ConflictError("Additions can only be executed on an active stage")
    if quantity <= 0:
        raise DomainError("Executed quantity must be positive", 422)
    payload = requirement.payload or {}
    now = utc_now()
    event = BrewAdditionEvent(
        brew_session_id=session.id,
        stage_instance_id=stage.id,
        requirement_id=requirement.requirement_id,
        planned_addition_id=(
            uuid.UUID(payload["source_addition_id"]) if payload.get("source_addition_id") else None
        ),
        source_addition_id=(
            uuid.UUID(payload["source_addition_id"]) if payload.get("source_addition_id") else None
        ),
        execution_status="EXECUTED",
        planned_amount=(
            Decimal(str(payload["planned_amount"])) if payload.get("planned_amount") else None
        ),
        planned_unit=payload.get("planned_unit"),
        actual_quantity=quantity,
        actual_unit=unit,
        actual_executed_at=executed_at or now,
        timing_basis=payload.get("timing_basis"),
        timing_offset_seconds=payload.get("timing_offset_seconds"),
        actual_ingredient_id=(
            uuid.UUID(payload["ingredient_id"]) if payload.get("ingredient_id") else None
        ),
        actual_lot_id=(
            uuid.UUID(payload["ingredient_lot_id"]) if payload.get("ingredient_lot_id") else None
        ),
        note=note,
        actor_user_id=user.id,
        operation_id=operation_id,
        late_entry=late,
        late_entry_reason=late_reason,
        recorded_at=now,
        available_at_original_stage_completion=not late,
        available_at_original_session_completion=session.status != "COMPLETED",
    )
    db.add(event)
    db.flush()
    requirement.status = "SATISFIED"
    requirement.satisfaction_source_type = "AdditionEvent"
    requirement.satisfaction_source_id = event.id
    apply_linked_reminder_requirements(
        db,
        stage,
        requirement,
        status="SATISFIED",
        source_type="AdditionEvent",
        source_id=event.id,
    )
    _complete_addition_reminder(
        db, stage, requirement, "AdditionEvent", event.id, user.id, "COMPLETED"
    )
    journal(
        db,
        session.id,
        "BREW_ADDITION_EXECUTED",
        f"Addition executed: {quantity} {unit}",
        stage.id,
        {"addition_event_id": str(event.id), "inventory_effect": False},
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_ADDITION_EXECUTED", "BrewAdditionEvent", event.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "execute_addition",
        "BrewStageRequirement",
        requirement.requirement_id,
        operation_id,
        document,
        {"id": str(event.id), "status": event.execution_status},
        "BrewAdditionEvent",
        event.id,
    )
    db.commit()
    db.refresh(event)
    return event


def skip_addition(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    requirement_id: uuid.UUID,
    reason: str,
    operation_id: str | None,
    expected_revision: int | None = None,
) -> BrewAdditionEvent:
    requirement, stage, session = _requirement(db, user, session_id, requirement_id)
    document = {
        "requirement_id": str(requirement_id),
        "reason": reason,
        "expected_revision": expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "skip_addition",
        "BrewStageRequirement",
        requirement.requirement_id,
        operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewAdditionEvent, replay.result_resource_id)
        if found:
            return found
    _lock_revision(session, expected_revision)
    if not reason or len(reason) < 10:
        raise DomainError("Skip requires a reason of at least 10 characters", 422)
    waiver = db.scalar(
        select(BrewWaiver).where(
            BrewWaiver.requirement_id == requirement.requirement_id,
            BrewWaiver.status == "ACTIVE",
        )
    )
    if requirement.required and waiver is None:
        raise ConflictError("Required additions can be skipped only with an active waiver")
    now = utc_now()
    event = BrewAdditionEvent(
        brew_session_id=session.id,
        stage_instance_id=stage.id,
        requirement_id=requirement.requirement_id,
        execution_status="SKIPPED",
        note=reason,
        actor_user_id=user.id,
        operation_id=operation_id,
        recorded_at=now,
    )
    db.add(event)
    db.flush()
    requirement.status = "WAIVED" if waiver else "SKIPPED"
    requirement.satisfaction_source_type = "Waiver" if waiver else "AdditionEvent"
    requirement.satisfaction_source_id = waiver.id if waiver else event.id
    apply_linked_reminder_requirements(
        db,
        stage,
        requirement,
        status=requirement.status,
        source_type=requirement.satisfaction_source_type,
        source_id=requirement.satisfaction_source_id,
    )
    _complete_addition_reminder(
        db,
        stage,
        requirement,
        "Waiver" if waiver else "AdditionEvent",
        waiver.id if waiver else event.id,
        user.id,
        "SKIPPED",
    )
    journal(
        db,
        session.id,
        "BREW_ADDITION_SKIPPED",
        "Planned addition skipped",
        stage.id,
        {"reason": reason},
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_ADDITION_SKIPPED", "BrewAdditionEvent", event.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "skip_addition",
        "BrewStageRequirement",
        requirement.requirement_id,
        operation_id,
        document,
        {"id": str(event.id), "status": event.execution_status},
        "BrewAdditionEvent",
        event.id,
    )
    db.commit()
    db.refresh(event)
    return event


def _effective_leaf(
    db: Session, original: BrewAdditionEvent
) -> BrewAdditionEvent | BrewAdditionCorrection:
    leaf: BrewAdditionEvent | BrewAdditionCorrection = original
    while True:
        nxt = db.scalar(
            select(BrewAdditionCorrection).where(BrewAdditionCorrection.correction_of_id == leaf.id)
        )
        if nxt is None:
            return leaf
        leaf = nxt


def correct_addition(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    addition_event_id: uuid.UUID,
    correction_of_id: uuid.UUID,
    reason: str,
    operation_id: str | None,
    execution_status: str | None = None,
    quantity: Decimal | None = None,
    unit: str | None = None,
    note: str | None = None,
    expected_revision: int | None = None,
) -> BrewAdditionCorrection:
    session = get_session(db, user, session_id)
    original = db.scalar(
        select(BrewAdditionEvent).where(
            BrewAdditionEvent.id == addition_event_id,
            BrewAdditionEvent.brew_session_id == session.id,
        )
    )
    if original is None:
        raise NotFoundError("Addition event not found")
    document = {
        "addition_event_id": str(addition_event_id),
        "correction_of_id": str(correction_of_id),
        "reason": reason,
        "execution_status": execution_status,
        "quantity": None if quantity is None else str(quantity),
        "unit": unit,
        "note": note,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "correct_addition",
        "BrewAdditionEvent",
        original.id,
        operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(BrewAdditionCorrection, replay.result_resource_id)
        if found:
            return found
    if not reason or not (10 <= len(reason) <= 1000):
        raise DomainError("Correction reason must be 10 to 1000 characters", 422)
    if expected_revision is not None and session.status not in {"COMPLETED", "ABORTED"}:
        if session.revision != expected_revision:
            raise ConflictError(
                "Stale session revision",
                code="STALE_REVISION",
                extra={"revision": session.revision},
            )
    if session.status in {"COMPLETED", "ABORTED"}:
        terminal = session.completed_at or session.aborted_at
        if terminal and utc_now() > _aware(terminal) + timedelta(days=30):
            raise ConflictError("Late entry window has closed", code="LATE_ENTRY_WINDOW_CLOSED")
    leaf = _effective_leaf(db, original)
    if leaf.id != correction_of_id:
        raise ConflictError(
            "Correction target has been superseded",
            code="ADDITION_CORRECTION_TARGET_SUPERSEDED",
            extra={"current_effective_id": str(leaf.id)},
        )
    current_status = getattr(leaf, "execution_status", original.execution_status)
    current_qty = getattr(leaf, "actual_quantity", original.actual_quantity)
    current_unit = getattr(leaf, "actual_unit", original.actual_unit)
    current_note = getattr(leaf, "note", original.note)
    current_when = getattr(leaf, "actual_executed_at", original.actual_executed_at)
    new_status = execution_status or current_status
    if new_status not in {"EXECUTED", "SKIPPED"}:
        raise DomainError("execution_status must be EXECUTED or SKIPPED", 422)
    changed = {}
    if execution_status and execution_status != current_status:
        changed["execution_status"] = execution_status
    if quantity is not None:
        changed["actual_quantity"] = str(quantity)
    if unit is not None:
        changed["actual_unit"] = unit
    if note is not None:
        changed["note"] = note
    if not changed:
        raise DomainError("Correction must change at least one field", 422)
    now = utc_now()
    correction = BrewAdditionCorrection(
        brew_session_id=session.id,
        stage_instance_id=original.stage_instance_id,
        original_addition_event_id=original.id,
        correction_of_id=leaf.id,
        execution_status=new_status,
        actual_quantity=current_qty if new_status == "SKIPPED" else (quantity or current_qty),
        actual_unit=current_unit if new_status == "SKIPPED" else (unit or current_unit),
        actual_executed_at=None if new_status == "SKIPPED" else current_when,
        note=note if note is not None else current_note,
        changed_fields=changed,
        reason=reason,
        actor_user_id=user.id,
        recorded_at=now,
        operation_id=operation_id,
        rule_version="phase3-addition-correction-v1",
        late_entry=session.status in {"COMPLETED", "ABORTED"},
    )
    db.add(correction)
    db.flush()
    requirement = db.scalar(
        select(BrewStageRequirement).where(
            BrewStageRequirement.requirement_id == original.requirement_id
        )
    )
    stage = db.get(BrewStage, original.stage_instance_id)
    if requirement and stage:
        if new_status == "EXECUTED":
            requirement.status = "SATISFIED"
            requirement.satisfaction_source_type = "AdditionCorrection"
            requirement.satisfaction_source_id = correction.id
            _complete_addition_reminder(
                db, stage, requirement, "AdditionCorrection", correction.id, user.id, "COMPLETED"
            )
        else:
            waiver = db.scalar(
                select(BrewWaiver).where(
                    BrewWaiver.requirement_id == requirement.requirement_id,
                    BrewWaiver.status == "ACTIVE",
                )
            )
            reminder = db.scalar(
                select(Notification).where(
                    Notification.requirement_id == requirement.requirement_id
                )
            )
            if reminder:
                prior = reminder.status
                reminder.status = "SKIPPED" if waiver else "DUE"
                reminder.satisfaction_source_id = None
                db.add(
                    BrewReminderHistory(
                        reminder_id=reminder.id,
                        prior_status=prior,
                        new_status=reminder.status,
                        cause="ADDITION_EVIDENCE_INVALIDATED",
                        actor_user_id=user.id,
                    )
                )
            requirement.status = "WAIVED" if waiver else "PENDING"
    journal(
        db,
        session.id,
        "BREW_ADDITION_CORRECTED",
        "Addition correction appended",
        original.stage_instance_id,
        {"correction_id": str(correction.id), "original_id": str(original.id)},
        actor_id=user.id,
        operation_id=operation_id,
    )
    audit(db, user.id, "BREW_ADDITION_CORRECTED", "BrewAdditionCorrection", correction.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "correct_addition",
        "BrewAdditionEvent",
        original.id,
        operation_id,
        document,
        {"id": str(correction.id), "status": correction.execution_status},
        "BrewAdditionCorrection",
        correction.id,
    )
    db.commit()
    db.refresh(correction)
    return correction


def inventory_transaction_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(InventoryTransaction)) or 0)
