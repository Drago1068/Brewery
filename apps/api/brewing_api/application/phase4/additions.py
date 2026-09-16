"""Phase 4 post-pitch additions (§21.2 / §24 / §31.1 / P4-FR-052–055/057/061/070)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.application.phase4.time_validation import (
    LATE_ENTRY_CLOSED_HOURS,
    LATE_ENTRY_STAGE_HOURS,
    _aware,
    _coerce_aware,
    assert_correction_window,
)
from brewing_api.application.phase4.waivers import supersede_waiver_by_evidence
from brewing_api.domain.fermentation.constants import (
    ADDITION_CORRECTION_SCHEMA_VERSION,
    ADDITION_SCHEDULE_SCHEMA_VERSION,
    TERMINAL_ADDITION_SCHEMA_VERSION,
)
from brewing_api.domain.fermentation.models import (
    FermentationAdditionCorrection,
    FermentationAdditionEvent,
    FermentationAdditionRequirement,
    FermentationJournalEvent,
    FermentationReminder,
    FermentationReminderHistory,
    FermentationSession,
    FermentationStageInstance,
)
from brewing_api.domain.identity.models import User
from brewing_api.domain.inventory.models import InventoryTransaction
from brewing_api.platform.time import utc_now

NORMAL_UNPLANNED_STATUSES = frozenset({"ACTIVE", "CONDITIONING"})


@dataclass(frozen=True)
class ExecutePlannedAdditionCommand:
    operation_id: str
    quantity: Decimal
    unit: str
    occurred_at: datetime
    note: str | None = None
    late_entry_reason: str | None = None
    expected_revision: int | None = None


@dataclass(frozen=True)
class RecordUnplannedAdditionCommand:
    operation_id: str
    quantity: Decimal
    unit: str
    occurred_at: datetime
    stage_instance_id: uuid.UUID | None = None
    ingredient_id: uuid.UUID | None = None
    lot_id: uuid.UUID | None = None
    note: str | None = None
    late_entry_reason: str | None = None
    expected_revision: int | None = None


@dataclass(frozen=True)
class CorrectAdditionCommand:
    operation_id: str
    correction_of_id: uuid.UUID
    reason: str
    execution_status: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    occurred_at: datetime | None = None
    note: str | None = None
    expected_revision: int | None = None


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def serialize_requirement(row: FermentationAdditionRequirement) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "requirement_id": str(row.requirement_id),
        "fermentation_session_id": str(row.fermentation_session_id),
        "stage_instance_id": str(row.stage_instance_id),
        "requirement_template_id": str(row.requirement_template_id),
        "requirement_class": row.requirement_class,
        "status": row.status,
        "required": row.required,
        "waivable": row.waivable,
        "source_recipe_ingredient_id": str(row.source_recipe_ingredient_id),
        "ingredient_id": str(row.ingredient_id),
        "ingredient_lot_id": None if row.ingredient_lot_id is None else str(row.ingredient_lot_id),
        "planned_amount": str(row.planned_amount),
        "planned_unit": row.planned_unit,
        "use_stage": row.use_stage,
        "timing_basis": row.timing_basis,
        "timing_offset_seconds": row.timing_offset_seconds,
        "planned_due_at": _iso(row.planned_due_at),
        "runtime_occurrence_policy": row.runtime_occurrence_policy,
        "reminder_id": None if row.reminder_id is None else str(row.reminder_id),
        "satisfaction_source_type": row.satisfaction_source_type,
        "satisfaction_source_id": None
        if row.satisfaction_source_id is None
        else str(row.satisfaction_source_id),
        "schema_version": row.schema_version,
    }


def serialize_addition_event(
    db: Session,
    event: FermentationAdditionEvent,
) -> dict[str, Any]:
    leaf = _effective_leaf(db, event)
    quantity = getattr(leaf, "actual_quantity", event.actual_quantity)
    unit = getattr(leaf, "actual_unit", event.actual_unit)
    occurred = getattr(leaf, "occurred_at", None)
    if occurred is None and hasattr(leaf, "actual_executed_at"):
        occurred = leaf.actual_executed_at
    if occurred is None:
        occurred = event.occurred_at
    note = getattr(leaf, "note", event.note)
    status = getattr(leaf, "execution_status", event.execution_status)
    return {
        "id": str(event.id),
        "fermentation_session_id": str(event.fermentation_session_id),
        "stage_instance_id": str(event.stage_instance_id),
        "requirement_id": None if event.requirement_id is None else str(event.requirement_id),
        "planned": event.planned,
        "execution_status": status,
        "planned_amount": None if event.planned_amount is None else str(event.planned_amount),
        "planned_unit": event.planned_unit,
        "actual_quantity": None if quantity is None else str(quantity),
        "actual_unit": unit,
        "occurred_at": _iso(occurred),
        "recorded_at": _iso(event.recorded_at),
        "timing_basis": event.timing_basis,
        "timing_offset_seconds": event.timing_offset_seconds,
        "actual_ingredient_id": None
        if event.actual_ingredient_id is None
        else str(event.actual_ingredient_id),
        "actual_lot_id": None if event.actual_lot_id is None else str(event.actual_lot_id),
        "note": note,
        "late_entry": event.late_entry,
        "late_entry_reason": event.late_entry_reason,
        "available_at_original_session_completion": event.available_at_original_session_completion,
        "terminal_state_at_recording": event.terminal_state_at_recording,
        "inventory_effect": event.inventory_effect,
        "operation_id": event.operation_id,
        "schema_version": event.schema_version,
        "current_correction_id": None if leaf is event else str(leaf.id),
    }


def serialize_correction(row: FermentationAdditionCorrection) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "fermentation_session_id": str(row.fermentation_session_id),
        "stage_instance_id": str(row.stage_instance_id),
        "original_addition_event_id": str(row.original_addition_event_id),
        "correction_of_id": str(row.correction_of_id),
        "execution_status": row.execution_status,
        "actual_quantity": None if row.actual_quantity is None else str(row.actual_quantity),
        "actual_unit": row.actual_unit,
        "occurred_at": _iso(row.occurred_at),
        "note": row.note,
        "changed_fields": row.changed_fields,
        "reason": row.reason,
        "recorded_at": _iso(row.recorded_at),
        "late_entry": row.late_entry,
        "operation_id": row.operation_id,
        "schema_version": row.schema_version,
    }


def list_session_requirements(
    db: Session, session_id: uuid.UUID
) -> list[FermentationAdditionRequirement]:
    return list(
        db.scalars(
            select(FermentationAdditionRequirement)
            .where(FermentationAdditionRequirement.fermentation_session_id == session_id)
            .order_by(
                FermentationAdditionRequirement.planned_due_at,
                FermentationAdditionRequirement.id,
            )
        ).all()
    )


def list_session_addition_events(
    db: Session, session_id: uuid.UUID
) -> list[FermentationAdditionEvent]:
    return list(
        db.scalars(
            select(FermentationAdditionEvent)
            .where(FermentationAdditionEvent.fermentation_session_id == session_id)
            .order_by(FermentationAdditionEvent.occurred_at, FermentationAdditionEvent.id)
        ).all()
    )


def inventory_transaction_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(InventoryTransaction)) or 0)


def inventory_consumption_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(InventoryTransaction)
            .where(InventoryTransaction.transaction_type == "CONSUMPTION")
        )
        or 0
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


def _parse_decimal(value: Decimal | str, field: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DomainError(f"Invalid numeric value for {field}", 422) from exc


def _effective_leaf(
    db: Session, original: FermentationAdditionEvent
) -> FermentationAdditionEvent | FermentationAdditionCorrection:
    leaf: FermentationAdditionEvent | FermentationAdditionCorrection = original
    while True:
        nxt = db.scalar(
            select(FermentationAdditionCorrection).where(
                FermentationAdditionCorrection.correction_of_id == leaf.id
            )
        )
        if nxt is None:
            return leaf
        leaf = nxt


def _complete_addition_reminder(
    db: Session,
    requirement: FermentationAdditionRequirement,
    *,
    source_type: str,
    source_id: uuid.UUID,
    actor_id: uuid.UUID,
    operation_id: str | None,
    status: str = "COMPLETED",
) -> None:
    if requirement.reminder_id is None:
        return
    reminder = db.get(FermentationReminder, requirement.reminder_id)
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
        FermentationReminderHistory(
            reminder_id=reminder.id,
            fermentation_session_id=requirement.fermentation_session_id,
            prior_status=prior,
            new_status=status,
            cause="ADDITION_EVENT" if status == "COMPLETED" else "ADDITION_SKIPPED",
            actor_user_id=actor_id,
            operation_id=operation_id,
        )
    )
    _journal(
        db,
        requirement.fermentation_session_id,
        "FERMENTATION_REMINDER_COMPLETED"
        if status == "COMPLETED"
        else "FERMENTATION_REMINDER_SKIPPED",
        reminder.message,
        actor_id=actor_id,
        operation_id=operation_id,
        stage_id=requirement.stage_instance_id,
        event_data={"reminder_id": str(reminder.id), "source_type": source_type},
    )


def _resolve_stage_for_unplanned(
    db: Session,
    session: FermentationSession,
    stage_instance_id: uuid.UUID | None,
) -> FermentationStageInstance:
    if stage_instance_id is not None:
        stage = db.get(FermentationStageInstance, stage_instance_id)
        if stage is None or stage.fermentation_session_id != session.id:
            raise NotFoundError("Stage instance not found")
        return stage
    preferred = "CONDITIONING" if session.status == "CONDITIONING" else "ACTIVE_FERMENTATION"
    stage = db.scalar(
        select(FermentationStageInstance).where(
            FermentationStageInstance.fermentation_session_id == session.id,
            FermentationStageInstance.canonical_stage_type == preferred,
        )
    )
    if stage is None:
        raise ConflictError("No eligible stage for unplanned addition", code="STAGE_NOT_ACTIVE")
    return stage


def _classify_addition_entry(
    session: FermentationSession,
    stage: FermentationStageInstance,
    *,
    occurred_at: datetime,
    late_entry_reason: str | None,
    server_now: datetime,
    require_revision: bool,
    expected_revision: int | None,
) -> tuple[bool, bool | None, str | None]:
    """Return (late_entry, available_at_original_session_completion, terminal_state)."""
    if session.status == "ABORTED":
        raise ConflictError(
            "New additions are prohibited on an aborted session",
            code="TERMINAL_SESSION_EVIDENCE_PROHIBITED",
        )

    if session.status == "CLOSED":
        if expected_revision is None:
            raise DomainError(
                "expected_revision is required for closed-session additions",
                422,
                code="EXPECTED_REVISION_REQUIRED",
            )
        if session.closed_at is None:
            raise DomainError("Closed session is missing closed_at", 409)
        closed_at = _coerce_aware(session.closed_at)
        if occurred_at > closed_at:
            raise DomainError(
                "Addition occurrence cannot be after session close",
                422,
                code="TERMINAL_ADDITION_OCCURRED_AFTER_CLOSE",
            )
        if server_now > closed_at + timedelta(hours=LATE_ENTRY_CLOSED_HOURS):
            raise ConflictError(
                "Late entry window has closed",
                code="LATE_ENTRY_WINDOW_CLOSED",
            )
        return True, False, "CLOSED"

    if session.status == "PAUSED":
        raise ConflictError(
            "Normal additions cannot be recorded while the session is paused",
            code="SESSION_PAUSED",
        )

    if stage.status == "COMPLETED":
        completed = stage.first_completed_at or stage.completed_at
        if completed is None:
            raise DomainError("Completed stage is missing completion timestamp", 409)
        if server_now > _coerce_aware(completed) + timedelta(hours=LATE_ENTRY_STAGE_HOURS):
            raise ConflictError(
                "Late entry window has closed",
                code="LATE_ENTRY_WINDOW_CLOSED",
            )
        if not late_entry_reason or not (10 <= len(late_entry_reason) <= 1000):
            raise DomainError("Late entry reason must be 10 to 1000 characters", 422)
        return True, True, None

    if stage.status not in {"ACTIVE", "PAUSED"}:
        raise ConflictError("Stage is not eligible for addition entry", code="STAGE_NOT_ACTIVE")

    return False, True if session.status not in {"CLOSED", "ABORTED"} else False, None


def execute_planned_addition(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    requirement_id: uuid.UUID,
    command: ExecutePlannedAdditionCommand,
) -> FermentationAdditionEvent:
    get_fermentation_session(db, user, session_id)
    document = {
        "requirement_id": str(requirement_id),
        "quantity": str(command.quantity),
        "unit": command.unit,
        "occurred_at": command.occurred_at.isoformat(),
        "note": command.note,
        "late_entry_reason": command.late_entry_reason,
        "expected_revision": command.expected_revision,
        "schema_version": TERMINAL_ADDITION_SCHEMA_VERSION,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "RecordPlannedAdditionExecution",
        "FermentationAdditionRequirement",
        requirement_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationAdditionEvent, replay.result_resource_id)
        if found:
            return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")

    requirement = db.scalar(
        select(FermentationAdditionRequirement).where(
            FermentationAdditionRequirement.requirement_id == requirement_id,
            FermentationAdditionRequirement.fermentation_session_id == session.id,
        )
    )
    if requirement is None:
        raise NotFoundError("Addition requirement not found")
    if requirement.status == "SATISFIED":
        raise ConflictError(
            "Planned addition already has an occurrence; runtime repeat is denied",
            code="RUNTIME_REPEAT_DENIED",
        )
    if requirement.runtime_occurrence_policy != "DO_NOT_COPY" and requirement.status != "PENDING":
        raise ConflictError(
            "Runtime repeat is denied for Phase 4 planned additions",
            code="RUNTIME_REPEAT_DENIED",
        )

    stage = db.get(FermentationStageInstance, requirement.stage_instance_id)
    if stage is None:
        raise NotFoundError("Stage instance not found")

    quantity = _parse_decimal(command.quantity, "quantity")
    if quantity <= 0:
        raise DomainError("Executed quantity must be positive", 422)
    occurred_at = _aware(command.occurred_at)
    now = utc_now()
    late_entry, available_at_completion, terminal_state = _classify_addition_entry(
        session,
        stage,
        occurred_at=occurred_at,
        late_entry_reason=command.late_entry_reason,
        server_now=now,
        require_revision=session.status == "CLOSED",
        expected_revision=command.expected_revision,
    )
    if session.status == "CLOSED" and command.expected_revision is None:
        raise DomainError(
            "expected_revision is required for closed-session additions",
            422,
            code="EXPECTED_REVISION_REQUIRED",
        )

    event = FermentationAdditionEvent(
        fermentation_session_id=session.id,
        stage_instance_id=stage.id,
        requirement_id=requirement.requirement_id,
        planned=True,
        execution_status="EXECUTED",
        planned_amount=requirement.planned_amount,
        planned_unit=requirement.planned_unit,
        actual_quantity=quantity,
        actual_unit=command.unit,
        occurred_at=occurred_at,
        recorded_at=now,
        timing_basis=requirement.timing_basis,
        timing_offset_seconds=requirement.timing_offset_seconds,
        actual_ingredient_id=requirement.ingredient_id,
        actual_lot_id=requirement.ingredient_lot_id,
        note=command.note,
        actor_user_id=user.id,
        operation_id=command.operation_id,
        late_entry=late_entry,
        late_entry_reason=command.late_entry_reason,
        available_at_original_session_completion=available_at_completion,
        terminal_state_at_recording=terminal_state,
        inventory_effect=False,
        schema_version=ADDITION_SCHEDULE_SCHEMA_VERSION,
    )
    db.add(event)
    db.flush()
    requirement.status = "SATISFIED"
    requirement.satisfaction_source_type = "FermentationAdditionEvent"
    requirement.satisfaction_source_id = event.id
    if requirement.reminder_id is not None:
        reminder = db.get(FermentationReminder, requirement.reminder_id)
        if reminder is not None:
            supersede_waiver_by_evidence(
                db,
                session,
                reminder=reminder,
                evidence_type="FermentationAdditionEvent",
                evidence_id=event.id,
                actor_id=user.id,
                operation_id=command.operation_id,
            )
    _complete_addition_reminder(
        db,
        requirement,
        source_type="FermentationAdditionEvent",
        source_id=event.id,
        actor_id=user.id,
        operation_id=command.operation_id,
    )
    session.revision += 1
    journal_data = {
        "addition_event_id": str(event.id),
        "requirement_id": str(requirement.requirement_id),
        "late_entry": late_entry,
        "inventory_effect": False,
        "planned": True,
    }
    if terminal_state:
        journal_data["terminal_state_at_recording"] = terminal_state
    _journal(
        db,
        session.id,
        "FERMENTATION_ADDITION_RECORDED",
        f"Planned addition executed: {quantity} {command.unit}",
        actor_id=user.id,
        operation_id=command.operation_id,
        stage_id=stage.id,
        occurred_at=occurred_at,
        event_data=journal_data,
    )
    audit(db, user.id, "FERMENTATION_ADDITION_RECORDED", "FermentationAdditionEvent", event.id)
    store_success(
        db,
        user.id,
        "RecordPlannedAdditionExecution",
        "FermentationAdditionRequirement",
        requirement_id,
        command.operation_id,
        document,
        serialize_addition_event(db, event),
        "FermentationAdditionEvent",
        event.id,
        http_status=201,
        terminal=session.status in {"CLOSED", "ABORTED"},
    )
    db.commit()
    db.refresh(event)
    return event


def record_unplanned_addition(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: RecordUnplannedAdditionCommand,
) -> FermentationAdditionEvent:
    get_fermentation_session(db, user, session_id)
    document = {
        "quantity": str(command.quantity),
        "unit": command.unit,
        "occurred_at": command.occurred_at.isoformat(),
        "stage_instance_id": None
        if command.stage_instance_id is None
        else str(command.stage_instance_id),
        "ingredient_id": None if command.ingredient_id is None else str(command.ingredient_id),
        "lot_id": None if command.lot_id is None else str(command.lot_id),
        "note": command.note,
        "late_entry_reason": command.late_entry_reason,
        "expected_revision": command.expected_revision,
        "schema_version": TERMINAL_ADDITION_SCHEMA_VERSION,
        "planned": False,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "RecordUnplannedAddition",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationAdditionEvent, replay.result_resource_id)
        if found:
            return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")

    quantity = _parse_decimal(command.quantity, "quantity")
    if quantity <= 0:
        raise DomainError("Executed quantity must be positive", 422)
    occurred_at = _aware(command.occurred_at)
    now = utc_now()
    stage = _resolve_stage_for_unplanned(db, session, command.stage_instance_id)

    # Normal unplanned only in ACTIVE/CONDITIONING; CLOSED uses §31; PAUSED denied.
    if session.status not in NORMAL_UNPLANNED_STATUSES | {"CLOSED"} and session.status != "PAUSED":
        if session.status == "ABORTED":
            raise ConflictError(
                "New additions are prohibited on an aborted session",
                code="TERMINAL_SESSION_EVIDENCE_PROHIBITED",
            )
        # Allow late entry after completed stage while nonterminal (§24).
        if stage.status != "COMPLETED":
            raise ConflictError(
                "Unplanned additions require ACTIVE or CONDITIONING session",
                code="INVALID_TRANSITION",
            )

    late_entry, available_at_completion, terminal_state = _classify_addition_entry(
        session,
        stage,
        occurred_at=occurred_at,
        late_entry_reason=command.late_entry_reason,
        server_now=now,
        require_revision=session.status == "CLOSED",
        expected_revision=command.expected_revision,
    )

    event = FermentationAdditionEvent(
        fermentation_session_id=session.id,
        stage_instance_id=stage.id,
        requirement_id=None,
        planned=False,
        execution_status="EXECUTED",
        planned_amount=None,
        planned_unit=None,
        actual_quantity=quantity,
        actual_unit=command.unit,
        occurred_at=occurred_at,
        recorded_at=now,
        timing_basis=None,
        timing_offset_seconds=None,
        actual_ingredient_id=command.ingredient_id,
        actual_lot_id=command.lot_id,
        note=command.note,
        actor_user_id=user.id,
        operation_id=command.operation_id,
        late_entry=late_entry,
        late_entry_reason=command.late_entry_reason,
        available_at_original_session_completion=available_at_completion,
        terminal_state_at_recording=terminal_state,
        inventory_effect=False,
        schema_version=ADDITION_SCHEDULE_SCHEMA_VERSION,
    )
    db.add(event)
    session.revision += 1
    db.flush()
    journal_data = {
        "addition_event_id": str(event.id),
        "late_entry": late_entry,
        "inventory_effect": False,
        "planned": False,
    }
    if terminal_state:
        journal_data["terminal_state_at_recording"] = terminal_state
    _journal(
        db,
        session.id,
        "FERMENTATION_ADDITION_RECORDED",
        f"Unplanned addition recorded: {quantity} {command.unit}",
        actor_id=user.id,
        operation_id=command.operation_id,
        stage_id=stage.id,
        occurred_at=occurred_at,
        event_data=journal_data,
    )
    audit(db, user.id, "FERMENTATION_ADDITION_RECORDED", "FermentationAdditionEvent", event.id)
    store_success(
        db,
        user.id,
        "RecordUnplannedAddition",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        serialize_addition_event(db, event),
        "FermentationAdditionEvent",
        event.id,
        http_status=201,
        terminal=session.status in {"CLOSED", "ABORTED"},
    )
    db.commit()
    db.refresh(event)
    return event


def correct_addition(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    addition_event_id: uuid.UUID,
    command: CorrectAdditionCommand,
) -> FermentationAdditionCorrection:
    get_fermentation_session(db, user, session_id)
    document = {
        "addition_event_id": str(addition_event_id),
        "correction_of_id": str(command.correction_of_id),
        "reason": command.reason,
        "execution_status": command.execution_status,
        "quantity": None if command.quantity is None else str(command.quantity),
        "unit": command.unit,
        "occurred_at": None if command.occurred_at is None else command.occurred_at.isoformat(),
        "note": command.note,
        "expected_revision": command.expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "CorrectAddition",
        "FermentationAdditionEvent",
        addition_event_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationAdditionCorrection, replay.result_resource_id)
        if found:
            return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    assert_correction_window(session)

    if not command.reason or not (10 <= len(command.reason) <= 1000):
        raise DomainError("Correction reason must be 10 to 1000 characters", 422)

    original = db.scalar(
        select(FermentationAdditionEvent).where(
            FermentationAdditionEvent.id == addition_event_id,
            FermentationAdditionEvent.fermentation_session_id == session.id,
        )
    )
    if original is None:
        raise NotFoundError("Addition event not found")

    leaf = _effective_leaf(db, original)
    if leaf.id != command.correction_of_id:
        raise ConflictError(
            "Correction target has been superseded",
            code="ADDITION_CORRECTION_TARGET_SUPERSEDED",
            extra={"current_effective_id": str(leaf.id)},
        )

    current_status = getattr(leaf, "execution_status", original.execution_status)
    current_qty = getattr(leaf, "actual_quantity", original.actual_quantity)
    current_unit = getattr(leaf, "actual_unit", original.actual_unit)
    current_note = getattr(leaf, "note", original.note)
    current_when = getattr(leaf, "occurred_at", original.occurred_at)
    new_status = command.execution_status or current_status
    if new_status not in {"EXECUTED", "SKIPPED"}:
        raise DomainError("execution_status must be EXECUTED or SKIPPED", 422)

    changed: dict[str, Any] = {}
    if command.execution_status and command.execution_status != current_status:
        changed["execution_status"] = command.execution_status
    if command.quantity is not None:
        changed["actual_quantity"] = str(command.quantity)
    if command.unit is not None:
        changed["actual_unit"] = command.unit
    if command.note is not None:
        changed["note"] = command.note
    if command.occurred_at is not None:
        changed["occurred_at"] = command.occurred_at.isoformat()
    if not changed:
        raise DomainError("Correction must change at least one field", 422)

    now = utc_now()
    correction = FermentationAdditionCorrection(
        fermentation_session_id=session.id,
        stage_instance_id=original.stage_instance_id,
        original_addition_event_id=original.id,
        correction_of_id=leaf.id,
        execution_status=new_status,
        actual_quantity=current_qty
        if new_status == "SKIPPED"
        else (command.quantity or current_qty),
        actual_unit=current_unit if new_status == "SKIPPED" else (command.unit or current_unit),
        occurred_at=None
        if new_status == "SKIPPED"
        else (_aware(command.occurred_at) if command.occurred_at else current_when),
        note=command.note if command.note is not None else current_note,
        changed_fields=changed,
        reason=command.reason,
        actor_user_id=user.id,
        recorded_at=now,
        operation_id=command.operation_id,
        late_entry=session.status in {"CLOSED", "ABORTED"},
        schema_version=ADDITION_CORRECTION_SCHEMA_VERSION,
    )
    db.add(correction)
    db.flush()

    if original.requirement_id is not None:
        requirement = db.scalar(
            select(FermentationAdditionRequirement).where(
                FermentationAdditionRequirement.requirement_id == original.requirement_id,
                FermentationAdditionRequirement.fermentation_session_id == session.id,
            )
        )
        if requirement is not None:
            if new_status == "EXECUTED":
                requirement.status = "SATISFIED"
                requirement.satisfaction_source_type = "FermentationAdditionCorrection"
                requirement.satisfaction_source_id = correction.id
                _complete_addition_reminder(
                    db,
                    requirement,
                    source_type="FermentationAdditionCorrection",
                    source_id=correction.id,
                    actor_id=user.id,
                    operation_id=command.operation_id,
                )
            else:
                requirement.status = "PENDING"
                requirement.satisfaction_source_type = None
                requirement.satisfaction_source_id = None
                if requirement.reminder_id is not None:
                    reminder = db.get(FermentationReminder, requirement.reminder_id)
                    if reminder is not None:
                        prior = reminder.status
                        reminder.status = "DUE"
                        reminder.satisfaction_source_type = None
                        reminder.satisfaction_source_id = None
                        reminder.completed_at = None
                        db.add(
                            FermentationReminderHistory(
                                reminder_id=reminder.id,
                                fermentation_session_id=session.id,
                                prior_status=prior,
                                new_status="DUE",
                                cause="ADDITION_EVIDENCE_INVALIDATED",
                                actor_user_id=user.id,
                                operation_id=command.operation_id,
                            )
                        )

    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_ADDITION_CORRECTED",
        "Addition correction appended",
        actor_id=user.id,
        operation_id=command.operation_id,
        stage_id=original.stage_instance_id,
        event_data={
            "correction_id": str(correction.id),
            "original_id": str(original.id),
        },
    )
    audit(
        db,
        user.id,
        "FERMENTATION_ADDITION_CORRECTED",
        "FermentationAdditionCorrection",
        correction.id,
    )
    store_success(
        db,
        user.id,
        "CorrectAddition",
        "FermentationAdditionEvent",
        addition_event_id,
        command.operation_id,
        document,
        serialize_correction(correction),
        "FermentationAdditionCorrection",
        correction.id,
        http_status=201,
    )
    db.commit()
    db.refresh(correction)
    return correction
