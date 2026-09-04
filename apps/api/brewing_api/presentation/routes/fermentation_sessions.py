import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from brewing_api.application.phase4 import (
    commands,
    completion,
    conditioning,
    measurements,
    og_consumption,
    read_models,
    reminders,
    timers,
    transitions,
    yeast,
)
from brewing_api.application.phase4.completion import CompleteFermentationCommand
from brewing_api.application.phase4.conditioning import ConditioningCommand
from brewing_api.application.phase4.measurements import CorrectionCommand, MeasurementCommand
from brewing_api.application.phase4.transitions import SessionCommand
from brewing_api.application.phase4.yeast import YeastEnrichCommand
from brewing_api.application.phase4.og_consumption import ReconcileOgCommand
from brewing_api.domain.fermentation.models import FermentationMeasurement
from brewing_api.presentation.dependencies import CurrentUser, Db

router = APIRouter(prefix="/fermentation-sessions", tags=["fermentation"])


class StartFermentationCommand(BaseModel):
    operation_id: str = Field(min_length=1, max_length=64)
    expected_brew_revision: int | None = Field(default=None, ge=0)


class RecordMeasurementCommand(BaseModel):
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


class CorrectMeasurementCommand(BaseModel):
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


class RevisionCommand(BaseModel):
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


class OperationOnlyCommand(BaseModel):
    operation_id: str = Field(min_length=1, max_length=64)


class EnrichYeastReferenceCommand(BaseModel):
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


class ReconcileOgCommandBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(min_length=1, max_length=64)
    brew_measurement_id: uuid.UUID
    expected_revision: int | None = Field(default=None, ge=0)


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
            value=Decimal(body.value),
            unit=body.unit,
            observed_at=body.observed_at,
            operation_id=body.operation_id,
            stage_instance_id=body.stage_instance_id,
            source=body.source,
            method=body.method,
            sample_temperature_c=None
            if body.sample_temperature_c is None
            else Decimal(body.sample_temperature_c),
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
            value=None if body.value is None else Decimal(body.value),
            unit=body.unit,
            observed_at=body.observed_at,
            method=body.method,
            sample_temperature_c=None
            if body.sample_temperature_c is None
            else Decimal(body.sample_temperature_c),
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
