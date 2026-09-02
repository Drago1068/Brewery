from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from calculations.fermentation import canonicalize_gravity, canonicalize_temperature
from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit
from brewing_api.application.phase4.derived_gravity import (
    effective_measurement_leaf,
    latest_derived_gravity,
    recompute_derived_gravity,
)
from brewing_api.application.phase4.completion import (
    gravity_change_affects_completion,
    invalidate_after_fermentation_affecting_evidence,
)
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.application.phase4.time_validation import (
    assert_correction_window,
    classify_late_entry,
    require_non_paused_for_new_measurement,
    validate_observed_at,
)
from brewing_api.domain.fermentation.constants import (
    GRAVITY_METHODS,
    MEASUREMENT_SCHEMA_VERSION,
    MEASUREMENT_SOURCES,
    MEASUREMENT_STAGE_BY_TYPE,
    MEASUREMENT_TYPES,
    PH_METHODS,
    TEMPERATURE_METHODS,
)
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationMeasurement,
    FermentationMeasurementCorrection,
    FermentationSession,
    FermentationStageInstance,
    FermentationYeastPitchReference,
)
from brewing_api.domain.identity.models import User
from brewing_api.platform.time import utc_now


@dataclass(frozen=True)
class MeasurementCommand:
    measurement_type: str
    value: Decimal
    unit: str
    observed_at: datetime
    operation_id: str
    stage_instance_id: uuid.UUID
    source: str = "OBSERVED"
    method: str | None = None
    sample_temperature_c: Decimal | None = None
    instrument_reference: str | None = None
    confidence: str | None = None
    note: str | None = None
    late_entry_reason: str | None = None
    expected_revision: int | None = None


@dataclass(frozen=True)
class CorrectionCommand:
    correction_of_id: uuid.UUID
    reason: str
    operation_id: str
    value: Decimal | None = None
    unit: str | None = None
    observed_at: datetime | None = None
    method: str | None = None
    sample_temperature_c: Decimal | None = None
    note: str | None = None
    expected_revision: int | None = None


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


def _stage_for_session(
    db: Session, session_id: uuid.UUID, stage_instance_id: uuid.UUID
) -> FermentationStageInstance:
    stage = db.get(FermentationStageInstance, stage_instance_id)
    if stage is None or stage.fermentation_session_id != session_id:
        raise NotFoundError("Stage instance not found")
    return stage


def _pitch_reference(db: Session, session_id: uuid.UUID) -> FermentationYeastPitchReference:
    pitch = db.scalar(
        select(FermentationYeastPitchReference).where(
            FermentationYeastPitchReference.fermentation_session_id == session_id
        )
    )
    if pitch is None:
        raise DomainError("Pitch reference is missing", 409)
    return pitch


def _parse_decimal(value: str | Decimal, field: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DomainError(f"Invalid numeric value for {field}", 422) from exc


def _validate_method(measurement_type: str, method: str | None) -> str:
    if not method:
        raise DomainError("Method is required", 422, code="MEASUREMENT_CONTEXT_REQUIRED")
    if measurement_type == "FERMENTATION_GRAVITY" and method not in GRAVITY_METHODS:
        raise DomainError("Unsupported gravity method", 422)
    if measurement_type in {"FERMENTATION_TEMPERATURE", "CONDITIONING_TEMPERATURE"} and method not in TEMPERATURE_METHODS:
        raise DomainError("Unsupported temperature method", 422)
    if measurement_type == "FERMENTATION_PH" and method not in PH_METHODS:
        raise DomainError("Unsupported pH method", 422)
    return method


def _canonicalize(
    measurement_type: str,
    raw_value: Decimal,
    raw_unit: str,
) -> tuple[Decimal, str, str | None]:
    if measurement_type == "FERMENTATION_GRAVITY":
        if raw_unit not in {"SG", "Plato"}:
            raise DomainError("Unsupported gravity unit", 422)
        try:
            canonical, model_id = canonicalize_gravity(raw_value, raw_unit)
        except ValueError as exc:
            code = str(exc)
            if code in {"PLATO_OUT_OF_DOMAIN", "PLATO_CONVERSION_FAILED", "GRAVITY_OUT_OF_DOMAIN"}:
                raise DomainError(code.replace("_", " ").title(), 422, code=code) from exc
            raise DomainError("Invalid gravity value", 422) from exc
        return canonical, "SG", model_id
    if measurement_type in {"FERMENTATION_TEMPERATURE", "CONDITIONING_TEMPERATURE"}:
        if raw_unit not in {"degC", "degF"}:
            raise DomainError("Unsupported temperature unit", 422)
        canonical = canonicalize_temperature(raw_value, raw_unit)
        low = Decimal("-5")
        high = Decimal("40") if measurement_type == "FERMENTATION_TEMPERATURE" else Decimal("30")
        if canonical < low or canonical > high:
            raise DomainError("Temperature is outside supported bounds", 422)
        return canonical, "degC", None
    if measurement_type == "FERMENTATION_PH":
        if raw_unit != "pH":
            raise DomainError("Unsupported pH unit", 422)
        if raw_value < Decimal("2.5") or raw_value > Decimal("8.0"):
            raise DomainError("pH is outside supported bounds", 422)
        return raw_value, "pH", None
    raise DomainError("Unsupported measurement type", 422)


def serialize_measurement(
    db: Session,
    measurement: FermentationMeasurement,
) -> dict:
    _, leaf_correction = effective_measurement_leaf(db, measurement)
    canonical_value = (
        leaf_correction.canonical_value if leaf_correction else measurement.canonical_value
    )
    canonical_unit = leaf_correction.canonical_unit if leaf_correction else measurement.canonical_unit
    observed_at = leaf_correction.observed_at if leaf_correction else measurement.observed_at
    conversion_model_id = (
        leaf_correction.conversion_model_id
        if leaf_correction
        else measurement.conversion_model_id
    )
    return {
        "id": str(measurement.id),
        "fermentation_session_id": str(measurement.fermentation_session_id),
        "stage_instance_id": str(measurement.stage_instance_id),
        "measurement_type": measurement.measurement_type,
        "raw_value": str(measurement.raw_value),
        "raw_unit": measurement.raw_unit,
        "canonical_value": str(canonical_value),
        "canonical_unit": canonical_unit,
        "conversion_model_id": conversion_model_id,
        "observed_at": observed_at,
        "recorded_at": measurement.recorded_at,
        "source": measurement.source,
        "method": measurement.method,
        "sample_temperature_c": None
        if measurement.sample_temperature_c is None
        else str(measurement.sample_temperature_c),
        "note": measurement.note,
        "late_entry": measurement.late_entry,
        "late_entry_reason": measurement.late_entry_reason,
        "operation_id": measurement.operation_id,
        "schema_version": measurement.schema_version,
        "current_correction_id": None if leaf_correction is None else str(leaf_correction.id),
    }


def record_measurement(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: MeasurementCommand,
) -> FermentationMeasurement:
    document = {
        "measurement_type": command.measurement_type,
        "value": str(command.value),
        "unit": command.unit,
        "observed_at": command.observed_at.isoformat(),
        "stage_instance_id": str(command.stage_instance_id),
        "method": command.method,
        "source": command.source,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "RecordMeasurement",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationMeasurement, replay.result_resource_id)
        if found:
            return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    require_non_paused_for_new_measurement(session)
    if command.measurement_type not in MEASUREMENT_TYPES:
        raise DomainError("Unsupported measurement type", 422)
    if command.source not in MEASUREMENT_SOURCES:
        raise DomainError("Unsupported measurement source", 422)

    stage = _stage_for_session(db, session.id, command.stage_instance_id)
    required_stage = MEASUREMENT_STAGE_BY_TYPE[command.measurement_type]
    if stage.canonical_stage_type != required_stage:
        raise DomainError(
            "Measurement type does not match stage",
            422,
            code="STAGE_TYPE_MISMATCH",
        )

    pitch = _pitch_reference(db, session.id)
    late_entry, available_at_completion = classify_late_entry(
        session,
        stage,
        late_entry_reason=command.late_entry_reason,
    )
    observed_at = validate_observed_at(
        command.observed_at,
        pitched_at=pitch.pitched_at,
        stage=stage,
    )
    method = _validate_method(command.measurement_type, command.method)
    canonical_value, canonical_unit, conversion_model_id = _canonicalize(
        command.measurement_type,
        command.value,
        command.unit,
    )
    now = utc_now()
    measurement = FermentationMeasurement(
        fermentation_session_id=session.id,
        stage_instance_id=stage.id,
        measurement_type=command.measurement_type,
        raw_value=command.value,
        raw_unit=command.unit,
        canonical_value=canonical_value,
        canonical_unit=canonical_unit,
        conversion_model_id=conversion_model_id,
        observed_at=observed_at,
        recorded_at=now,
        actor_user_id=user.id,
        source=command.source,
        instrument_reference=command.instrument_reference,
        confidence=command.confidence,
        note=command.note,
        method=method,
        sample_temperature_c=command.sample_temperature_c,
        validation_status="ACCEPTED",
        late_entry=late_entry,
        late_entry_reason=command.late_entry_reason,
        operation_id=command.operation_id,
        schema_version=MEASUREMENT_SCHEMA_VERSION,
        available_at_original_session_completion=available_at_completion,
    )
    db.add(measurement)
    session.revision += 1
    if command.measurement_type == "FERMENTATION_GRAVITY":
        prior = latest_derived_gravity(db, session.id)
        prior_stable = prior.stable_gravity_status if prior else None
        prior_attenuation = prior.apparent_attenuation_ratio if prior else None
        recompute_derived_gravity(db, session.id)
        if gravity_change_affects_completion(
            db,
            session,
            prior_stable_status=prior_stable,
            prior_attenuation=prior_attenuation,
        ):
            invalidate_after_fermentation_affecting_evidence(
                db,
                session,
                cause_id=measurement.id,
                actor_id=user.id,
            )
    _journal(
        db,
        session.id,
        "FERMENTATION_MEASUREMENT_RECORDED",
        f"{command.measurement_type} recorded",
        actor_id=user.id,
        operation_id=command.operation_id,
        stage_id=stage.id,
        occurred_at=observed_at,
        event_data={"measurement_id": str(measurement.id), "late_entry": late_entry},
    )
    audit(db, user.id, "FERMENTATION_MEASUREMENT_RECORDED", "FermentationMeasurement", session.id)
    db.flush()
    store_success(
        db,
        user.id,
        "RecordMeasurement",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        {"id": str(measurement.id)},
        "FermentationMeasurement",
        measurement.id,
        http_status=201,
    )
    db.commit()
    db.refresh(measurement)
    return measurement


def correct_measurement(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    measurement_id: uuid.UUID,
    command: CorrectionCommand,
) -> FermentationMeasurementCorrection:
    measurement = db.scalar(
        select(FermentationMeasurement).where(
            FermentationMeasurement.id == measurement_id,
            FermentationMeasurement.fermentation_session_id == session_id,
        )
    )
    if measurement is None:
        raise NotFoundError("Measurement not found")
    document = {
        "measurement_id": str(measurement_id),
        "correction_of_id": str(command.correction_of_id),
        "reason": command.reason,
        "value": None if command.value is None else str(command.value),
        "unit": command.unit,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "CorrectMeasurement",
        "FermentationMeasurement",
        measurement.id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationMeasurementCorrection, replay.result_resource_id)
        if found:
            return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    assert_correction_window(session)
    if not command.reason or not (10 <= len(command.reason) <= 1000):
        raise DomainError("Correction reason must be 10 to 1000 characters", 422)

    _, leaf = effective_measurement_leaf(db, measurement)
    current_leaf_id = leaf.id if leaf else measurement.id
    if current_leaf_id != command.correction_of_id:
        raise ConflictError(
            "Correction target has been superseded",
            code="CORRECTION_TARGET_SUPERSEDED",
            extra={"current_effective_id": str(current_leaf_id)},
        )

    raw_value = command.value if command.value is not None else (leaf.raw_value if leaf else measurement.raw_value)
    raw_unit = command.unit or (leaf.raw_unit if leaf else measurement.raw_unit)
    observed_at = command.observed_at or (leaf.observed_at if leaf else measurement.observed_at)
    method = command.method or (leaf.method if leaf else measurement.method)
    note = command.note if command.note is not None else (leaf.note if leaf else measurement.note)
    sample_temperature_c = (
        command.sample_temperature_c
        if command.sample_temperature_c is not None
        else (leaf.sample_temperature_c if leaf else measurement.sample_temperature_c)
    )
    note_only = (
        measurement.measurement_type != "FERMENTATION_GRAVITY"
        or (
            command.value is None
            and command.unit is None
            and command.observed_at is None
            and command.method is None
            and command.sample_temperature_c is None
        )
    )
    source = leaf.source if leaf else measurement.source
    instrument_reference = leaf.instrument_reference if leaf else measurement.instrument_reference
    confidence = leaf.confidence if leaf else measurement.confidence

    pitch = _pitch_reference(db, session.id)
    stage = _stage_for_session(db, session.id, measurement.stage_instance_id)
    observed_at = validate_observed_at(
        observed_at,
        pitched_at=pitch.pitched_at,
        stage=stage,
        require_explicit_offset=False,
    )
    method = _validate_method(measurement.measurement_type, method)
    canonical_value, canonical_unit, conversion_model_id = _canonicalize(
        measurement.measurement_type,
        raw_value,
        raw_unit,
    )
    now = utc_now()
    correction = FermentationMeasurementCorrection(
        fermentation_session_id=session.id,
        stage_instance_id=measurement.stage_instance_id,
        correction_of_id=current_leaf_id,
        measurement_type=measurement.measurement_type,
        raw_value=raw_value,
        raw_unit=raw_unit,
        canonical_value=canonical_value,
        canonical_unit=canonical_unit,
        conversion_model_id=conversion_model_id,
        observed_at=observed_at,
        recorded_at=now,
        actor_user_id=user.id,
        source=source,
        instrument_reference=instrument_reference,
        confidence=confidence,
        note=note,
        method=method,
        sample_temperature_c=sample_temperature_c,
        reason=command.reason,
        operation_id=command.operation_id,
        schema_version=MEASUREMENT_SCHEMA_VERSION,
    )
    db.add(correction)
    session.revision += 1
    if measurement.measurement_type == "FERMENTATION_GRAVITY" and not note_only:
        prior = latest_derived_gravity(db, session.id)
        prior_stable = prior.stable_gravity_status if prior else None
        prior_attenuation = prior.apparent_attenuation_ratio if prior else None
        recompute_derived_gravity(db, session.id)
        if session.status in {
            "FERMENTATION_COMPLETE",
            "CONDITIONING",
            "CONDITIONING_COMPLETE",
            "COMPLETION_ASSESSED",
            "HANDOFF_READY",
            "CLOSED",
        } or gravity_change_affects_completion(
            db,
            session,
            prior_stable_status=prior_stable,
            prior_attenuation=prior_attenuation,
        ):
            invalidate_after_fermentation_affecting_evidence(
                db,
                session,
                cause_id=correction.id,
                actor_id=user.id,
            )
    elif measurement.measurement_type == "FERMENTATION_GRAVITY":
        recompute_derived_gravity(db, session.id)
    _journal(
        db,
        session.id,
        "FERMENTATION_MEASUREMENT_CORRECTED",
        f"{measurement.measurement_type} corrected",
        actor_id=user.id,
        operation_id=command.operation_id,
        stage_id=measurement.stage_instance_id,
        occurred_at=observed_at,
        event_data={
            "measurement_id": str(measurement.id),
            "correction_id": str(correction.id),
            "correction_of_id": str(current_leaf_id),
        },
    )
    audit(db, user.id, "FERMENTATION_MEASUREMENT_CORRECTED", "FermentationMeasurementCorrection", session.id)
    db.flush()
    store_success(
        db,
        user.id,
        "CorrectMeasurement",
        "FermentationMeasurement",
        measurement.id,
        command.operation_id,
        document,
        {"id": str(correction.id), "measurement_id": str(measurement.id)},
        "FermentationMeasurementCorrection",
        correction.id,
        http_status=201,
    )
    db.commit()
    db.refresh(correction)
    return correction
