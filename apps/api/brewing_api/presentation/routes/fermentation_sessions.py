import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from brewing_api.application.phase4 import commands, completion, measurements, read_models, transitions
from brewing_api.application.phase4.completion import CompleteFermentationCommand
from brewing_api.application.phase4.measurements import CorrectionCommand, MeasurementCommand
from brewing_api.application.phase4.transitions import SessionCommand
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
