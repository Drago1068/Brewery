import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import Response
from pydantic import Field

from brewing_api.application.errors import DomainError
from brewing_api.application.phase4 import (
    actions,
    additions,
    commands,
    completion,
    conditioning,
    measurements,
    og_consumption,
    read_models,
    readiness,
    reminders,
    timers,
    transitions,
    waivers,
    yeast,
)
from brewing_api.application.phase4 import (
    export as phase4_export,
)
from brewing_api.application.phase4 import (
    media as phase4_media,
)
from brewing_api.application.phase4 import (
    notes as phase4_notes,
)
from brewing_api.application.phase4 import (
    sessions as phase4_sessions,
)
from brewing_api.application.phase4.actions import RecordActionCommand
from brewing_api.application.phase4.additions import (
    CorrectAdditionCommand,
    ExecutePlannedAdditionCommand,
    RecordUnplannedAdditionCommand,
)
from brewing_api.application.phase4.completion import CompleteFermentationCommand
from brewing_api.application.phase4.conditioning import ConditioningCommand
from brewing_api.application.phase4.journal import merged_journal_events
from brewing_api.application.phase4.measurements import CorrectionCommand, MeasurementCommand
from brewing_api.application.phase4.og_consumption import ReconcileOgCommand
from brewing_api.application.phase4.readiness import AssessReadinessCommand, RecordHandoffCommand
from brewing_api.application.phase4.sessions import (
    get_fermentation_session as load_fermentation_session,
)
from brewing_api.application.phase4.transitions import SessionCommand
from brewing_api.application.phase4.waivers import RecordWaiverCommand
from brewing_api.application.phase4.yeast import YeastEnrichCommand
from brewing_api.domain.fermentation.models import FermentationMeasurement
from brewing_api.presentation.dependencies import CurrentUser, Db
from brewing_api.presentation.phase4_schemas import Phase4ClosedCommand

router = APIRouter(prefix="/fermentation-sessions", tags=["fermentation"])


def _parse_decimal_field(raw: str, field: str) -> Decimal:
    """Parse a client-supplied numeric string with deterministic 422 semantics.

    Slice 2 remediation (F-002): malformed strings and non-finite values must
    fail closed as validation errors, never as unhandled ``Decimal``
    ``InvalidOperation`` (HTTP 500).
    """
    try:
        parsed = Decimal(raw)
    except InvalidOperation as exc:
        raise DomainError(
            f"Invalid numeric value for {field}", 422, code="INVALID_NUMERIC_VALUE"
        ) from exc
    if not parsed.is_finite():
        raise DomainError(f"Invalid numeric value for {field}", 422, code="INVALID_NUMERIC_VALUE")
    return parsed


class StartFermentationCommand(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    expected_brew_revision: int | None = Field(default=None, ge=0)
    equipment_profile_id: uuid.UUID | None = None


class RecordMeasurementCommand(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    measurement_type: str
    value: str
    unit: str
    observed_at: datetime
    stage_instance_id: uuid.UUID
    source: str = "OBSERVED"
    method: str | None = None
    sample_temperature_c: str | None = None
    instrument_reference: str | None = None
    confidence: str | None = None
    note: str | None = None
    late_entry_reason: str | None = None
    expected_revision: int | None = Field(default=None, ge=0)


class CorrectMeasurementCommand(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    correction_of_id: uuid.UUID
    reason: str
    value: str | None = None
    unit: str | None = None
    observed_at: datetime | None = None
    method: str | None = None
    sample_temperature_c: str | None = None
    note: str | None = None
    expected_revision: int | None = Field(default=None, ge=0)


class RevisionCommand(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    expected_revision: int | None = Field(default=None, ge=0)


class AbortCommand(RevisionCommand):
    reason: str


class CompleteFermentationRequest(RevisionCommand):
    override: bool = False
    override_reason: str | None = None


class CompleteConditioningRequest(RevisionCommand):
    override: bool = False
    override_reason: str | None = None


class RecordWaiverRequest(RevisionCommand):
    reason: str
    requirement_id: uuid.UUID | None = None
    requirement_class: str | None = None
    supplemental_note: str | None = None


class AssessPackagingReadinessRequest(RevisionCommand):
    override: bool = False
    override_reason: str | None = None


class RecordPackagingHandoffRequest(RevisionCommand):
    assessment_id: uuid.UUID


class StartAuxiliaryTimerCommand(RevisionCommand):
    stage_instance_id: uuid.UUID
    name: str = Field(min_length=1, max_length=80)
    planned_duration_seconds: int = Field(gt=0)
    clock_basis: str = "WALL_CLOCK"


class CancelTimerCommand(RevisionCommand):
    reason: str


class ExtendTimerCommand(RevisionCommand):
    extra_seconds: int = Field(gt=0)
    reason: str


class OperationOnlyCommand(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)


class CreateNoteCommand(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    body: str = Field(min_length=1, max_length=4000)
    stage_instance_id: uuid.UUID | None = None
    expected_revision: int | None = Field(default=None, ge=0)


class RemoveAttachmentCommand(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=1000)


class EnrichYeastReferenceCommand(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    expected_revision: int | None = Field(default=None, ge=0)
    ingredient_lot_id: uuid.UUID | None = None
    preparation_method_note: str | None = None
    pitch_inputs: dict | None = None
    field_provenance: dict | None = None
    declaration_note: str | None = None
    source_fermentation_session_id: uuid.UUID | None = None
    source_yeast_reference_id: uuid.UUID | None = None
    reason: str | None = None


class ReconcileOgCommandBody(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    brew_measurement_id: uuid.UUID
    expected_revision: int | None = Field(default=None, ge=0)


class RecordActionRequest(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    action_type: str
    occurred_at: datetime
    note: str | None = None
    stage_instance_id: uuid.UUID | None = None
    expected_revision: int | None = Field(default=None, ge=0)


class ExecutePlannedAdditionRequest(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    quantity: str
    unit: str
    occurred_at: datetime
    note: str | None = None
    late_entry_reason: str | None = None
    expected_revision: int | None = Field(default=None, ge=0)


class RecordUnplannedAdditionRequest(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    quantity: str
    unit: str
    occurred_at: datetime
    stage_instance_id: uuid.UUID | None = None
    ingredient_id: uuid.UUID | None = None
    lot_id: uuid.UUID | None = None
    note: str | None = None
    late_entry_reason: str | None = None
    expected_revision: int | None = Field(default=None, ge=0)


class CorrectAdditionRequest(Phase4ClosedCommand):
    operation_id: str = Field(min_length=1, max_length=64)
    correction_of_id: uuid.UUID
    reason: str
    execution_status: str | None = None
    quantity: str | None = None
    unit: str | None = None
    occurred_at: datetime | None = None
    note: str | None = None
    expected_revision: int | None = Field(default=None, ge=0)


@router.get("")
def list_fermentation_sessions(user: CurrentUser, db: Db) -> list[dict]:
    """P4 §30 ListSessions — owner index for worksheet navigation (Slice 13)."""
    rows = phase4_sessions.list_fermentation_sessions(db, user)
    return [phase4_sessions.serialize_session_summary(row) for row in rows]


@router.post(
    "/brew-sessions/{brew_session_id}/start",
    status_code=status.HTTP_201_CREATED,
)
def start_fermentation_session(
    brew_session_id: uuid.UUID,
    body: StartFermentationCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    session = commands.start_fermentation_session(
        db,
        user,
        brew_session_id,
        operation_id=body.operation_id,
        expected_brew_revision=body.expected_brew_revision,
        equipment_profile_id=body.equipment_profile_id,
    )
    return read_models.serialize_session(db, user, session.id)


@router.get("/pitch-history")
def get_pitch_history(
    user: CurrentUser,
    db: Db,
    session_id: uuid.UUID | None = None,
    lot_id: uuid.UUID | None = None,
) -> list[dict]:
    return yeast.pitch_history(db, user, session_id=session_id, lot_id=lot_id)


@router.post("/{fermentation_session_id}/yeast-reference", status_code=status.HTTP_200_OK)
def enrich_yeast_reference(
    fermentation_session_id: uuid.UUID,
    body: EnrichYeastReferenceCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    reference = yeast.enrich_yeast_reference(
        db,
        user,
        fermentation_session_id,
        YeastEnrichCommand(
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
            ingredient_lot_id=body.ingredient_lot_id,
            preparation_method_note=body.preparation_method_note,
            pitch_inputs=body.pitch_inputs,
            field_provenance=body.field_provenance,
            declaration_note=body.declaration_note,
            source_fermentation_session_id=body.source_fermentation_session_id,
            source_yeast_reference_id=body.source_yeast_reference_id,
            reason=body.reason,
        ),
    )
    serialized = yeast.serialize_yeast_reference(reference)
    assert serialized is not None
    return serialized


@router.post("/{fermentation_session_id}/og-consumption", status_code=status.HTTP_200_OK)
def reconcile_upstream_original_gravity(
    fermentation_session_id: uuid.UUID,
    body: ReconcileOgCommandBody,
    user: CurrentUser,
    db: Db,
) -> dict:
    row = og_consumption.reconcile_upstream_original_gravity(
        db,
        user,
        fermentation_session_id,
        ReconcileOgCommand(
            operation_id=body.operation_id,
            brew_measurement_id=body.brew_measurement_id,
            expected_revision=body.expected_revision,
        ),
    )
    return {
        "session": read_models.serialize_session(db, user, fermentation_session_id),
        "og_consumption": og_consumption.serialize_og_consumption(row),
    }


@router.get("/{fermentation_session_id}")
def get_fermentation_session(
    fermentation_session_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
) -> dict:
    return read_models.serialize_session(db, user, fermentation_session_id)


@router.post("/{fermentation_session_id}/measurements", status_code=status.HTTP_201_CREATED)
def record_measurement(
    fermentation_session_id: uuid.UUID,
    body: RecordMeasurementCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    measurement = measurements.record_measurement(
        db,
        user,
        fermentation_session_id,
        MeasurementCommand(
            measurement_type=body.measurement_type,
            value=_parse_decimal_field(body.value, "value"),
            unit=body.unit,
            observed_at=body.observed_at,
            operation_id=body.operation_id,
            stage_instance_id=body.stage_instance_id,
            source=body.source,
            method=body.method,
            sample_temperature_c=None
            if body.sample_temperature_c is None
            else _parse_decimal_field(body.sample_temperature_c, "sample_temperature_c"),
            instrument_reference=body.instrument_reference,
            confidence=body.confidence,
            note=body.note,
            late_entry_reason=body.late_entry_reason,
            expected_revision=body.expected_revision,
        ),
    )
    return measurements.serialize_measurement(db, measurement)


@router.post(
    "/{fermentation_session_id}/measurements/{measurement_id}/corrections",
    status_code=status.HTTP_201_CREATED,
)
def correct_measurement(
    fermentation_session_id: uuid.UUID,
    measurement_id: uuid.UUID,
    body: CorrectMeasurementCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    correction = measurements.correct_measurement(
        db,
        user,
        fermentation_session_id,
        measurement_id,
        CorrectionCommand(
            correction_of_id=body.correction_of_id,
            reason=body.reason,
            operation_id=body.operation_id,
            value=None if body.value is None else _parse_decimal_field(body.value, "value"),
            unit=body.unit,
            observed_at=body.observed_at,
            method=body.method,
            sample_temperature_c=None
            if body.sample_temperature_c is None
            else _parse_decimal_field(body.sample_temperature_c, "sample_temperature_c"),
            note=body.note,
            expected_revision=body.expected_revision,
        ),
    )
    original = db.get(FermentationMeasurement, measurement_id)
    assert original is not None
    payload = measurements.serialize_measurement(db, original)
    payload["correction_id"] = str(correction.id)
    payload["reason"] = correction.reason
    return payload


@router.post("/{fermentation_session_id}/actions", status_code=status.HTTP_201_CREATED)
def record_action(
    fermentation_session_id: uuid.UUID,
    body: RecordActionRequest,
    user: CurrentUser,
    db: Db,
) -> dict:
    action = actions.record_action(
        db,
        user,
        fermentation_session_id,
        RecordActionCommand(
            operation_id=body.operation_id,
            action_type=body.action_type,
            occurred_at=body.occurred_at,
            note=body.note,
            stage_instance_id=body.stage_instance_id,
            expected_revision=body.expected_revision,
        ),
    )
    return actions.serialize_action(action)


@router.post(
    "/{fermentation_session_id}/additions/{requirement_id}/execute",
    status_code=status.HTTP_201_CREATED,
)
def execute_planned_addition(
    fermentation_session_id: uuid.UUID,
    requirement_id: uuid.UUID,
    body: ExecutePlannedAdditionRequest,
    user: CurrentUser,
    db: Db,
) -> dict:
    event = additions.execute_planned_addition(
        db,
        user,
        fermentation_session_id,
        requirement_id,
        ExecutePlannedAdditionCommand(
            operation_id=body.operation_id,
            quantity=Decimal(body.quantity),
            unit=body.unit,
            occurred_at=body.occurred_at,
            note=body.note,
            late_entry_reason=body.late_entry_reason,
            expected_revision=body.expected_revision,
        ),
    )
    return additions.serialize_addition_event(db, event)


@router.post(
    "/{fermentation_session_id}/additions/unplanned",
    status_code=status.HTTP_201_CREATED,
)
def record_unplanned_addition(
    fermentation_session_id: uuid.UUID,
    body: RecordUnplannedAdditionRequest,
    user: CurrentUser,
    db: Db,
) -> dict:
    event = additions.record_unplanned_addition(
        db,
        user,
        fermentation_session_id,
        RecordUnplannedAdditionCommand(
            operation_id=body.operation_id,
            quantity=Decimal(body.quantity),
            unit=body.unit,
            occurred_at=body.occurred_at,
            stage_instance_id=body.stage_instance_id,
            ingredient_id=body.ingredient_id,
            lot_id=body.lot_id,
            note=body.note,
            late_entry_reason=body.late_entry_reason,
            expected_revision=body.expected_revision,
        ),
    )
    return additions.serialize_addition_event(db, event)


@router.post(
    "/{fermentation_session_id}/addition-events/{addition_event_id}/corrections",
    status_code=status.HTTP_201_CREATED,
)
def correct_addition(
    fermentation_session_id: uuid.UUID,
    addition_event_id: uuid.UUID,
    body: CorrectAdditionRequest,
    user: CurrentUser,
    db: Db,
) -> dict:
    correction = additions.correct_addition(
        db,
        user,
        fermentation_session_id,
        addition_event_id,
        CorrectAdditionCommand(
            operation_id=body.operation_id,
            correction_of_id=body.correction_of_id,
            reason=body.reason,
            execution_status=body.execution_status,
            quantity=None if body.quantity is None else Decimal(body.quantity),
            unit=body.unit,
            occurred_at=body.occurred_at,
            note=body.note,
            expected_revision=body.expected_revision,
        ),
    )
    return additions.serialize_correction(correction)


@router.post("/{fermentation_session_id}/commands/pause")
def pause_fermentation_session(
    fermentation_session_id: uuid.UUID,
    body: RevisionCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    transitions.pause_fermentation_session(
        db,
        user,
        fermentation_session_id,
        SessionCommand(
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
        ),
    )
    return read_models.serialize_session(db, user, fermentation_session_id)


@router.post("/{fermentation_session_id}/commands/resume")
def resume_fermentation_session(
    fermentation_session_id: uuid.UUID,
    body: RevisionCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    transitions.resume_fermentation_session(
        db,
        user,
        fermentation_session_id,
        SessionCommand(
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
        ),
    )
    return read_models.serialize_session(db, user, fermentation_session_id)


@router.post("/{fermentation_session_id}/commands/abort")
def abort_fermentation_session(
    fermentation_session_id: uuid.UUID,
    body: AbortCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    transitions.abort_fermentation_session(
        db,
        user,
        fermentation_session_id,
        SessionCommand(
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
            reason=body.reason,
        ),
    )
    return read_models.serialize_session(db, user, fermentation_session_id)


@router.post("/{fermentation_session_id}/commands/close")
def close_fermentation_session(
    fermentation_session_id: uuid.UUID,
    body: RevisionCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    transitions.close_fermentation_session(
        db,
        user,
        fermentation_session_id,
        SessionCommand(
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
        ),
    )
    return read_models.serialize_session(db, user, fermentation_session_id)


@router.post("/{fermentation_session_id}/commands/complete-fermentation")
def complete_fermentation(
    fermentation_session_id: uuid.UUID,
    body: CompleteFermentationRequest,
    user: CurrentUser,
    db: Db,
) -> dict:
    session, assessment = completion.complete_fermentation(
        db,
        user,
        fermentation_session_id,
        CompleteFermentationCommand(
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
            override=body.override,
            override_reason=body.override_reason,
        ),
    )
    payload = read_models.serialize_session(db, user, session.id)
    payload["completion_assessment"] = completion.serialize_assessment(assessment)
    return payload


@router.post("/{fermentation_session_id}/commands/start-conditioning")
def start_conditioning(
    fermentation_session_id: uuid.UUID,
    body: RevisionCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    session = conditioning.start_conditioning(
        db,
        user,
        fermentation_session_id,
        ConditioningCommand(
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
        ),
    )
    return read_models.serialize_session(db, user, session.id)


@router.post("/{fermentation_session_id}/commands/skip-conditioning")
def skip_conditioning(
    fermentation_session_id: uuid.UUID,
    body: RevisionCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    session, assessment = conditioning.skip_conditioning(
        db,
        user,
        fermentation_session_id,
        ConditioningCommand(
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
        ),
    )
    payload = read_models.serialize_session(db, user, session.id)
    payload["conditioning_assessment"] = completion.serialize_assessment(assessment)
    return payload


@router.post("/{fermentation_session_id}/commands/complete-conditioning")
def complete_conditioning(
    fermentation_session_id: uuid.UUID,
    body: CompleteConditioningRequest,
    user: CurrentUser,
    db: Db,
) -> dict:
    session, assessment = conditioning.complete_conditioning(
        db,
        user,
        fermentation_session_id,
        ConditioningCommand(
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
            override=body.override,
            override_reason=body.override_reason,
        ),
    )
    payload = read_models.serialize_session(db, user, session.id)
    payload["conditioning_assessment"] = completion.serialize_assessment(assessment)
    return payload


@router.post("/{fermentation_session_id}/waivers", status_code=status.HTTP_201_CREATED)
def record_waiver(
    fermentation_session_id: uuid.UUID,
    body: RecordWaiverRequest,
    user: CurrentUser,
    db: Db,
) -> dict:
    waiver = waivers.record_waiver(
        db,
        user,
        fermentation_session_id,
        RecordWaiverCommand(
            operation_id=body.operation_id,
            reason=body.reason,
            requirement_id=body.requirement_id,
            requirement_class=body.requirement_class,
            expected_revision=body.expected_revision,
            supplemental_note=body.supplemental_note,
        ),
    )
    return waivers.serialize_waiver(waiver)


@router.post("/{fermentation_session_id}/commands/assess-packaging-readiness")
def assess_packaging_readiness(
    fermentation_session_id: uuid.UUID,
    body: AssessPackagingReadinessRequest,
    user: CurrentUser,
    db: Db,
) -> dict:
    session, assessment = readiness.assess_packaging_readiness(
        db,
        user,
        fermentation_session_id,
        AssessReadinessCommand(
            operation_id=body.operation_id,
            expected_revision=body.expected_revision,
            override=body.override,
            override_reason=body.override_reason,
        ),
    )
    payload = read_models.serialize_session(db, user, session.id)
    payload["packaging_readiness_assessment"] = completion.serialize_assessment(assessment)
    return payload


@router.post("/{fermentation_session_id}/commands/record-packaging-readiness-handoff")
def record_packaging_readiness_handoff(
    fermentation_session_id: uuid.UUID,
    body: RecordPackagingHandoffRequest,
    user: CurrentUser,
    db: Db,
) -> dict:
    session, handoff = readiness.record_packaging_readiness_handoff(
        db,
        user,
        fermentation_session_id,
        RecordHandoffCommand(
            operation_id=body.operation_id,
            assessment_id=body.assessment_id,
            expected_revision=body.expected_revision,
        ),
    )
    payload = read_models.serialize_session(db, user, session.id)
    payload["packaging_readiness_handoff"] = readiness.serialize_handoff(handoff)
    return payload


@router.post(
    "/{fermentation_session_id}/timers",
    status_code=status.HTTP_201_CREATED,
)
def start_auxiliary_timer(
    fermentation_session_id: uuid.UUID,
    body: StartAuxiliaryTimerCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    timer = timers.start_auxiliary_timer(
        db,
        user,
        fermentation_session_id,
        stage_instance_id=body.stage_instance_id,
        name=body.name,
        planned_duration_seconds=body.planned_duration_seconds,
        operation_id=body.operation_id,
        clock_basis=body.clock_basis,
        expected_revision=body.expected_revision,
    )
    return timers.serialize_timer(timer)


@router.post("/timers/{timer_id}/pause")
def pause_timer(
    timer_id: uuid.UUID,
    body: RevisionCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    timer = timers.pause_timer(
        db,
        user,
        timer_id,
        operation_id=body.operation_id,
        expected_revision=body.expected_revision,
    )
    return timers.serialize_timer(timer)


@router.post("/timers/{timer_id}/resume")
def resume_timer(
    timer_id: uuid.UUID,
    body: RevisionCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    timer = timers.resume_timer(
        db,
        user,
        timer_id,
        operation_id=body.operation_id,
        expected_revision=body.expected_revision,
    )
    return timers.serialize_timer(timer)


@router.post("/timers/{timer_id}/complete")
def complete_timer(
    timer_id: uuid.UUID,
    body: RevisionCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    timer = timers.complete_timer(
        db,
        user,
        timer_id,
        operation_id=body.operation_id,
        expected_revision=body.expected_revision,
    )
    return timers.serialize_timer(timer)


@router.post("/timers/{timer_id}/cancel")
def cancel_timer(
    timer_id: uuid.UUID,
    body: CancelTimerCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    timer = timers.cancel_timer(
        db,
        user,
        timer_id,
        operation_id=body.operation_id,
        reason=body.reason,
        expected_revision=body.expected_revision,
    )
    return timers.serialize_timer(timer)


@router.post("/timers/{timer_id}/acknowledge")
def acknowledge_timer(
    timer_id: uuid.UUID,
    body: OperationOnlyCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    timer = timers.acknowledge_timer(
        db,
        user,
        timer_id,
        operation_id=body.operation_id,
    )
    return timers.serialize_timer(timer)


@router.post("/timers/{timer_id}/extend")
def extend_timer(
    timer_id: uuid.UUID,
    body: ExtendTimerCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    timer = timers.extend_timer(
        db,
        user,
        timer_id,
        operation_id=body.operation_id,
        extra_seconds=body.extra_seconds,
        reason=body.reason,
        expected_revision=body.expected_revision,
    )
    return timers.serialize_timer(timer)


@router.post("/reminders/{reminder_id}/acknowledge")
def acknowledge_reminder(
    reminder_id: uuid.UUID,
    body: RevisionCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    reminder = reminders.acknowledge_reminder(
        db,
        user,
        reminder_id,
        operation_id=body.operation_id,
        expected_revision=body.expected_revision,
    )
    return reminders.serialize_reminder(reminder)


@router.post("/{session_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(session_id: uuid.UUID, body: CreateNoteCommand, user: CurrentUser, db: Db) -> dict:
    note = phase4_notes.create_note(
        db,
        user,
        session_id,
        body.body,
        operation_id=body.operation_id,
        stage_id=body.stage_instance_id,
        expected_revision=body.expected_revision,
    )
    return phase4_notes.serialize_note(note)


@router.post("/{session_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    session_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    operation_id: Annotated[str, Form()],
    caption: Annotated[str | None, Form()] = None,
    stage_id: Annotated[uuid.UUID | None, Form()] = None,
) -> dict:
    attachment = phase4_media.upload_attachment(
        db, user, session_id, file, operation_id, caption, stage_id
    )
    return phase4_media.serialize_attachment(attachment)


@router.get("/{session_id}/attachments")
def list_attachments(session_id: uuid.UUID, user: CurrentUser, db: Db) -> dict:
    session = load_fermentation_session(db, user, session_id)
    items = phase4_media.list_session_attachments(db, session.id)
    return {"items": [phase4_media.serialize_attachment(item) for item in items]}


@router.get("/{session_id}/attachments/{attachment_id}")
def get_attachment(
    session_id: uuid.UUID, attachment_id: uuid.UUID, user: CurrentUser, db: Db
) -> Response:
    return phase4_media.retrieve_attachment(db, user, session_id, attachment_id)


@router.post("/{session_id}/attachments/{attachment_id}/remove")
def remove_attachment(
    session_id: uuid.UUID,
    attachment_id: uuid.UUID,
    body: RemoveAttachmentCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    attachment = phase4_media.soft_remove_attachment(
        db,
        user,
        session_id,
        attachment_id,
        body.reason,
        body.operation_id,
    )
    return phase4_media.serialize_attachment(attachment)


@router.get("/{session_id}/journal")
def get_journal(session_id: uuid.UUID, user: CurrentUser, db: Db) -> dict:
    session = load_fermentation_session(db, user, session_id)
    return {"items": merged_journal_events(db, session)}


@router.get("/{session_id}/export")
def export_session(session_id: uuid.UUID, user: CurrentUser, db: Db, format: str = "json") -> dict:
    return phase4_export.export_session(db, user, session_id, format=format)
