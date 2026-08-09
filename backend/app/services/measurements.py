"""Measurement requirement generation and mutation services (E2A-3 / ADR-005)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import (
    BrewPlan,
    BrewSession,
    BrewStageOccurrence,
    MeasurementDefinition,
    MeasurementObservationHistory,
    MeasurementRecord,
    MeasurementRequirement,
    MeasurementStatusHistory,
)
from app.domain import measurement as measurement_domain
from app.domain.brew_day import json_safe
from app.domain.enums import (
    BrewEventType,
    MeasurementConfidence,
    MeasurementObservationEventClass,
    MeasurementRequirementLevel,
    MeasurementRequirementStatus,
    MeasurementValidationClass,
    MeasurementValueKind,
)
from app.schemas.brew_day import (
    InstrumentCorrectionRequest,
    MeasurementCaptureRequest,
    MeasurementMissRequest,
    MeasurementRevisionRequest,
    MeasurementWaiveRequest,
)
from app.services import brew_events as brew_events_service
from app.services import brew_session as brew_session_service
from app.services import idempotency as idempotency_service

SCOPE_BREW_SESSION = "BREW_SESSION"


def _illegal(code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": code, "message": message, **extra},
    )


def _iso_attr(obj: Any, attr: str) -> Optional[str]:
    """Read datetime attrs without triggering async lazy IO on expired columns."""
    insp = sa_inspect(obj)
    if attr in insp.unloaded:
        return None
    value = getattr(obj, attr)
    return value.isoformat() if value is not None else None


def _record_to_dict(record: MeasurementRecord) -> dict:
    display, display_unit = measurement_domain.display_value(record)
    return {
        "id": record.id,
        "requirement_id": record.requirement_id,
        "brew_session_id": record.brew_session_id,
        "raw_value": record.raw_value,
        "raw_unit": record.raw_unit,
        "corrected_value": record.corrected_value,
        "corrected_unit": record.corrected_unit,
        "display_value": display,
        "display_unit": display_unit,
        "value_kind": record.value_kind,
        "confidence": record.confidence,
        "instrument": record.instrument,
        "method": record.method,
        "provenance": record.provenance,
        "validation_class": record.validation_class,
        "validation_notes": record.validation_notes,
        "latest_observation_history_id": record.latest_observation_history_id,
        "first_captured_at": _iso_attr(record, "first_captured_at"),
        "captured_by": record.captured_by,
        "client_submission_id": record.client_submission_id,
        "updated_at": _iso_attr(record, "updated_at"),
    }


def _requirement_to_dict(req: MeasurementRequirement) -> dict:
    return {
        "id": req.id,
        "brew_session_id": req.brew_session_id,
        "stage_occurrence_id": req.stage_occurrence_id,
        "measurement_definition_id": req.measurement_definition_id,
        "measurement_code": req.measurement_code,
        "requirement_level": req.requirement_level,
        "planned_value": req.planned_value,
        "planned_unit": req.planned_unit,
        "planned_kind": req.planned_kind,
        "validation_min": str(req.validation_min) if req.validation_min is not None else None,
        "validation_max": str(req.validation_max) if req.validation_max is not None else None,
        "status": req.status,
        "created_at": _iso_attr(req, "created_at"),
        "record": _record_to_dict(req.record) if req.record is not None else None,
    }


async def generate_requirements_for_session(
    db: AsyncSession,
    *,
    session: BrewSession,
    plan: BrewPlan,
) -> list[MeasurementRequirement]:
    """Create deterministic MeasurementRequirements from active definitions + plan snapshot."""
    defs = (
        await db.execute(
            select(MeasurementDefinition).where(MeasurementDefinition.is_active.is_(True))
        )
    ).scalars().all()
    stages_by_code = {s.stage_code: s for s in session.stage_occurrences}
    plan_view = {
        "planned_calculation_snapshot": plan.planned_calculation_snapshot,
        "recipe_snapshot": plan.recipe_snapshot,
    }
    created: list[MeasurementRequirement] = []
    for definition in defs:
        stage = stages_by_code.get(definition.typical_stage_code)
        if stage is None:
            continue
        planned_value, planned_unit, planned_kind = measurement_domain.planned_from_brew_plan(
            plan_view, definition.code
        )
        req = MeasurementRequirement(
            brew_session_id=session.id,
            stage_occurrence_id=stage.id,
            measurement_definition_id=definition.id,
            measurement_code=definition.code,
            requirement_level=definition.default_requirement_level,
            planned_value=planned_value,
            planned_unit=planned_unit,
            planned_kind=planned_kind,
            validation_min=definition.expected_min,
            validation_max=definition.expected_max,
            status=MeasurementRequirementStatus.PENDING,
        )
        db.add(req)
        created.append(req)
    await db.flush()
    return created


async def _load_requirement(db: AsyncSession, requirement_id: str) -> MeasurementRequirement:
    result = await db.execute(
        select(MeasurementRequirement)
        .where(MeasurementRequirement.id == requirement_id)
        .options(selectinload(MeasurementRequirement.record))
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status_code=404, detail="MeasurementRequirement not found")
    return req


async def _load_session_for_mutation(
    db: AsyncSession, session_id: str, expected_version: int
) -> BrewSession:
    session = await brew_session_service.get_brew_session(db, session_id)
    if expected_version != session.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONCURRENCY_CONFLICT",
                "message": "expected_session_version does not match current BrewSession.version",
                "expected_session_version": expected_version,
                "current_session_version": session.version,
            },
        )
    return session


async def _append_status(
    db: AsyncSession,
    *,
    requirement: MeasurementRequirement,
    from_status: str,
    to_status: str,
    actor_id: str,
    source_command: str,
    reason: Optional[str],
    client_submission_id: Optional[str],
    client_occurred_at: Optional[datetime],
    payload: Optional[dict] = None,
) -> MeasurementStatusHistory:
    row = MeasurementStatusHistory(
        requirement_id=requirement.id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        actor_id=actor_id,
        source_command=source_command,
        client_submission_id=client_submission_id,
        client_occurred_at=client_occurred_at,
        payload=json_safe(payload) if payload else None,
    )
    db.add(row)
    requirement.status = to_status
    await db.flush()
    return row


async def list_session_requirements(db: AsyncSession, session_id: str) -> list[dict]:
    await brew_session_service.get_brew_session(db, session_id)
    result = await db.execute(
        select(MeasurementRequirement)
        .where(MeasurementRequirement.brew_session_id == session_id)
        .options(selectinload(MeasurementRequirement.record))
        .order_by(MeasurementRequirement.measurement_code.asc())
    )
    return [_requirement_to_dict(r) for r in result.scalars().all()]


async def list_observation_history(db: AsyncSession, requirement_id: str) -> list[dict]:
    await _load_requirement(db, requirement_id)
    rows = (
        await db.execute(
            select(MeasurementObservationHistory)
            .where(MeasurementObservationHistory.requirement_id == requirement_id)
            .order_by(
                MeasurementObservationHistory.occurred_at.asc(),
                MeasurementObservationHistory.id.asc(),
            )
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "requirement_id": r.requirement_id,
            "measurement_record_id": r.measurement_record_id,
            "event_class": r.event_class,
            "raw_value": r.raw_value,
            "raw_unit": r.raw_unit,
            "corrected_value": r.corrected_value,
            "corrected_unit": r.corrected_unit,
            "confidence": r.confidence,
            "instrument": r.instrument,
            "method": r.method,
            "provenance": r.provenance,
            "validation_class": r.validation_class,
            "validation_notes": r.validation_notes,
            "reason": r.reason,
            "actor_id": r.actor_id,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "client_occurred_at": r.client_occurred_at.isoformat()
            if r.client_occurred_at
            else None,
            "client_submission_id": r.client_submission_id,
            "payload": r.payload,
        }
        for r in rows
    ]


async def list_status_history(db: AsyncSession, requirement_id: str) -> list[dict]:
    await _load_requirement(db, requirement_id)
    rows = (
        await db.execute(
            select(MeasurementStatusHistory)
            .where(MeasurementStatusHistory.requirement_id == requirement_id)
            .order_by(
                MeasurementStatusHistory.occurred_at.asc(),
                MeasurementStatusHistory.id.asc(),
            )
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "requirement_id": r.requirement_id,
            "from_status": r.from_status,
            "to_status": r.to_status,
            "reason": r.reason,
            "actor_id": r.actor_id,
            "source_command": r.source_command,
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "client_occurred_at": r.client_occurred_at.isoformat()
            if r.client_occurred_at
            else None,
            "client_submission_id": r.client_submission_id,
            "payload": r.payload,
        }
        for r in rows
    ]


async def capture_measurement(
    db: AsyncSession,
    session_id: str,
    payload: MeasurementCaptureRequest,
) -> dict:
    fp = idempotency_service.fingerprint_payload(payload.model_dump(mode="json"))
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing, operation_type="CAPTURE_MEASUREMENT", request_fingerprint=fp
    )
    if replay is not None:
        return replay

    session = await _load_session_for_mutation(db, session_id, payload.expected_session_version)
    req = await _load_requirement(db, payload.requirement_id)
    if req.brew_session_id != session_id:
        raise HTTPException(status_code=404, detail="MeasurementRequirement not found for session")
    if req.status != MeasurementRequirementStatus.PENDING:
        raise _illegal(
            "REQUIREMENT_NOT_PENDING",
            f"Capture requires PENDING requirement; found {req.status}",
            status=req.status,
        )

    try:
        MeasurementConfidence(payload.confidence)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_CONFIDENCE",
                "message": "confidence must be HIGH, MEDIUM, or LOW",
            },
        ) from exc

    validation = measurement_domain.validate_capture(
        raw_value=payload.raw_value,
        raw_unit=payload.raw_unit,
        measurement_code=req.measurement_code,
        validation_min=req.validation_min,
        validation_max=req.validation_max,
    )
    if validation.input_error:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "MEASUREMENT_INPUT_ERROR",
                "message": validation.notes,
                "validation_class": MeasurementValidationClass.INPUT_ERROR,
            },
        )

    actor = settings.default_actor_id
    now = datetime.now(timezone.utc)
    version_before = session.version

    record = MeasurementRecord(
        requirement_id=req.id,
        brew_session_id=session.id,
        raw_value=str(payload.raw_value).strip(),
        raw_unit=payload.raw_unit.strip(),
        corrected_value=None,
        corrected_unit=None,
        value_kind=MeasurementValueKind.MEASURED,
        confidence=payload.confidence,
        instrument=payload.instrument,
        method=payload.method,
        provenance=json_safe(payload.provenance) if payload.provenance else None,
        validation_class=validation.validation_class,
        validation_notes=validation.notes,
        first_captured_at=now,
        captured_by=actor,
        client_submission_id=payload.client_submission_id,
        updated_at=now,
    )
    db.add(record)
    await db.flush()
    req.record = record

    obs = MeasurementObservationHistory(
        requirement_id=req.id,
        measurement_record_id=record.id,
        event_class=MeasurementObservationEventClass.RAW_CAPTURE,
        raw_value=record.raw_value,
        raw_unit=record.raw_unit,
        corrected_value=None,
        corrected_unit=None,
        confidence=record.confidence,
        instrument=record.instrument,
        method=record.method,
        provenance=record.provenance,
        validation_class=validation.validation_class,
        validation_notes=validation.notes,
        actor_id=actor,
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
        payload={"source_command": "CAPTURE_MEASUREMENT"},
    )
    db.add(obs)
    await db.flush()
    record.latest_observation_history_id = obs.id

    await _append_status(
        db,
        requirement=req,
        from_status=MeasurementRequirementStatus.PENDING,
        to_status=MeasurementRequirementStatus.CAPTURED,
        actor_id=actor,
        source_command="CAPTURE_MEASUREMENT",
        reason=None,
        client_submission_id=payload.client_submission_id,
        client_occurred_at=payload.client_occurred_at,
    )

    await brew_events_service.append_brew_event(
        db,
        brewery_id=session.brewery_id,
        brew_plan_id=session.brew_plan_id,
        brew_session_id=session.id,
        event_type=BrewEventType.MEASUREMENT_CAPTURED,
        actor_id=actor,
        payload={
            "requirement_id": req.id,
            "measurement_record_id": record.id,
            "measurement_code": req.measurement_code,
            "observation_history_id": obs.id,
        },
        client_submission_id=payload.client_submission_id,
        client_occurred_at=payload.client_occurred_at,
    )
    if validation.validation_class in (
        MeasurementValidationClass.UNUSUAL_VALUE,
        MeasurementValidationClass.DOMAIN_CONCERN,
    ):
        await brew_events_service.append_brew_event(
            db,
            brewery_id=session.brewery_id,
            brew_plan_id=session.brew_plan_id,
            brew_session_id=session.id,
            event_type=BrewEventType.VALIDATION_WARNING,
            actor_id=actor,
            payload={
                "requirement_id": req.id,
                "validation_class": validation.validation_class,
                "notes": validation.notes,
            },
            client_submission_id=payload.client_submission_id,
            client_occurred_at=payload.client_occurred_at,
        )

    session.version = version_before + 1
    response = {
        "requirement": _requirement_to_dict(req),
        "record": _record_to_dict(record),
        "session_version": session.version,
    }
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
        operation_type="CAPTURE_MEASUREMENT",
        request_fingerprint=fp,
        resource_type="MeasurementRecord",
        resource_id=record.id,
        http_status=201,
        response_snapshot=response,
        actor_id=actor,
        session_version_before=version_before,
        session_version_after=session.version,
    )
    await db.commit()
    return response


async def instrument_correction(
    db: AsyncSession,
    record_id: str,
    payload: InstrumentCorrectionRequest,
) -> dict:
    fp = idempotency_service.fingerprint_payload(payload.model_dump(mode="json"))
    record = await db.get(MeasurementRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MeasurementRecord not found")
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=record.brew_session_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing, operation_type="INSTRUMENT_CORRECTION", request_fingerprint=fp
    )
    if replay is not None:
        return replay

    session = await _load_session_for_mutation(
        db, record.brew_session_id, payload.expected_session_version
    )
    req = await _load_requirement(db, record.requirement_id)
    actor = settings.default_actor_id
    version_before = session.version

    obs = MeasurementObservationHistory(
        requirement_id=req.id,
        measurement_record_id=record.id,
        event_class=MeasurementObservationEventClass.INSTRUMENT_CORRECTION,
        raw_value=record.raw_value,
        raw_unit=record.raw_unit,
        corrected_value=str(payload.corrected_value).strip(),
        corrected_unit=payload.corrected_unit.strip(),
        confidence=record.confidence,
        instrument=payload.instrument or record.instrument,
        method=payload.method or record.method,
        provenance=json_safe(payload.provenance) if payload.provenance else record.provenance,
        validation_class=record.validation_class,
        validation_notes=record.validation_notes,
        reason=payload.reason,
        actor_id=actor,
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
        payload={"source_command": "INSTRUMENT_CORRECTION"},
    )
    db.add(obs)
    await db.flush()
    record.corrected_value = obs.corrected_value
    record.corrected_unit = obs.corrected_unit
    record.latest_observation_history_id = obs.id
    if payload.instrument:
        record.instrument = payload.instrument
    if payload.method:
        record.method = payload.method

    await brew_events_service.append_brew_event(
        db,
        brewery_id=session.brewery_id,
        brew_plan_id=session.brew_plan_id,
        brew_session_id=session.id,
        event_type=BrewEventType.MEASUREMENT_INSTRUMENT_CORRECTION,
        actor_id=actor,
        payload={
            "requirement_id": req.id,
            "measurement_record_id": record.id,
            "observation_history_id": obs.id,
        },
        client_submission_id=payload.client_submission_id,
        client_occurred_at=payload.client_occurred_at,
    )
    session.version = version_before + 1
    response = {"record": _record_to_dict(record), "session_version": session.version}
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session.id,
        client_submission_id=payload.client_submission_id,
        operation_type="INSTRUMENT_CORRECTION",
        request_fingerprint=fp,
        resource_type="MeasurementRecord",
        resource_id=record.id,
        http_status=200,
        response_snapshot=response,
        actor_id=actor,
        session_version_before=version_before,
        session_version_after=session.version,
    )
    await db.commit()
    return response


async def user_revision(
    db: AsyncSession,
    record_id: str,
    payload: MeasurementRevisionRequest,
) -> dict:
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "REVISION_REASON_REQUIRED", "message": "reason is required"},
        )
    fp = idempotency_service.fingerprint_payload(payload.model_dump(mode="json"))
    record = await db.get(MeasurementRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="MeasurementRecord not found")
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=record.brew_session_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing, operation_type="USER_REVISION", request_fingerprint=fp
    )
    if replay is not None:
        return replay

    session = await _load_session_for_mutation(
        db, record.brew_session_id, payload.expected_session_version
    )
    req = await _load_requirement(db, record.requirement_id)
    actor = settings.default_actor_id
    version_before = session.version

    new_raw = str(payload.raw_value).strip()
    new_unit = payload.raw_unit.strip()
    obs = MeasurementObservationHistory(
        requirement_id=req.id,
        measurement_record_id=record.id,
        event_class=MeasurementObservationEventClass.USER_REVISION,
        raw_value=new_raw,
        raw_unit=new_unit,
        corrected_value=record.corrected_value,
        corrected_unit=record.corrected_unit,
        confidence=payload.confidence or record.confidence,
        instrument=record.instrument,
        method=record.method,
        provenance=record.provenance,
        validation_class=record.validation_class,
        validation_notes=record.validation_notes,
        reason=payload.reason.strip(),
        actor_id=actor,
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
        payload={
            "source_command": "USER_REVISION",
            "prior_raw_value": record.raw_value,
            "prior_raw_unit": record.raw_unit,
        },
    )
    db.add(obs)
    await db.flush()
    record.raw_value = new_raw
    record.raw_unit = new_unit
    if payload.confidence:
        record.confidence = payload.confidence
    record.latest_observation_history_id = obs.id

    await brew_events_service.append_brew_event(
        db,
        brewery_id=session.brewery_id,
        brew_plan_id=session.brew_plan_id,
        brew_session_id=session.id,
        event_type=BrewEventType.MEASUREMENT_USER_REVISION,
        actor_id=actor,
        payload={
            "requirement_id": req.id,
            "measurement_record_id": record.id,
            "observation_history_id": obs.id,
            "reason": payload.reason.strip(),
        },
        client_submission_id=payload.client_submission_id,
        client_occurred_at=payload.client_occurred_at,
    )
    session.version = version_before + 1
    response = {"record": _record_to_dict(record), "session_version": session.version}
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session.id,
        client_submission_id=payload.client_submission_id,
        operation_type="USER_REVISION",
        request_fingerprint=fp,
        resource_type="MeasurementRecord",
        resource_id=record.id,
        http_status=200,
        response_snapshot=response,
        actor_id=actor,
        session_version_before=version_before,
        session_version_after=session.version,
    )
    await db.commit()
    return response


async def miss_requirement(
    db: AsyncSession,
    requirement_id: str,
    payload: MeasurementMissRequest,
) -> dict:
    return await _lifecycle_transition(
        db,
        requirement_id=requirement_id,
        payload=payload,
        operation="MISS_MEASUREMENT",
        to_status=MeasurementRequirementStatus.MISSED,
        event_type=BrewEventType.MEASUREMENT_MISSED,
        reason=payload.reason,
        require_reason=False,
    )


async def waive_requirement(
    db: AsyncSession,
    requirement_id: str,
    payload: MeasurementWaiveRequest,
) -> dict:
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "WAIVE_REASON_REQUIRED", "message": "reason is required"},
        )
    return await _lifecycle_transition(
        db,
        requirement_id=requirement_id,
        payload=payload,
        operation="WAIVE_MEASUREMENT",
        to_status=MeasurementRequirementStatus.WAIVED,
        event_type=BrewEventType.MEASUREMENT_WAIVED,
        reason=payload.reason.strip(),
        require_reason=True,
    )


async def _lifecycle_transition(
    db: AsyncSession,
    *,
    requirement_id: str,
    payload: MeasurementMissRequest | MeasurementWaiveRequest,
    operation: str,
    to_status: str,
    event_type: str,
    reason: Optional[str],
    require_reason: bool,
) -> dict:
    fp = idempotency_service.fingerprint_payload(payload.model_dump(mode="json"))
    req = await _load_requirement(db, requirement_id)
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=req.brew_session_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing, operation_type=operation, request_fingerprint=fp
    )
    if replay is not None:
        return replay

    session = await _load_session_for_mutation(
        db, req.brew_session_id, payload.expected_session_version
    )
    if req.status != MeasurementRequirementStatus.PENDING:
        raise _illegal(
            "REQUIREMENT_NOT_PENDING",
            f"{operation} requires PENDING; found {req.status}",
            status=req.status,
        )
    actor = settings.default_actor_id
    version_before = session.version
    await _append_status(
        db,
        requirement=req,
        from_status=MeasurementRequirementStatus.PENDING,
        to_status=to_status,
        actor_id=actor,
        source_command=operation,
        reason=reason,
        client_submission_id=payload.client_submission_id,
        client_occurred_at=payload.client_occurred_at,
    )
    await brew_events_service.append_brew_event(
        db,
        brewery_id=session.brewery_id,
        brew_plan_id=session.brew_plan_id,
        brew_session_id=session.id,
        event_type=event_type,
        actor_id=actor,
        payload={
            "requirement_id": req.id,
            "measurement_code": req.measurement_code,
            "reason": reason,
        },
        client_submission_id=payload.client_submission_id,
        client_occurred_at=payload.client_occurred_at,
    )
    session.version = version_before + 1
    response = {"requirement": _requirement_to_dict(req), "session_version": session.version}
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session.id,
        client_submission_id=payload.client_submission_id,
        operation_type=operation,
        request_fingerprint=fp,
        resource_type="MeasurementRequirement",
        resource_id=req.id,
        http_status=200,
        response_snapshot=response,
        actor_id=actor,
        session_version_before=version_before,
        session_version_after=session.version,
    )
    await db.commit()
    return response


async def auto_miss_required_for_skipped_stage(
    db: AsyncSession,
    *,
    session: BrewSession,
    stage: BrewStageOccurrence,
    actor_id: str,
    client_submission_id: Optional[str],
    client_occurred_at: Optional[datetime],
) -> None:
    """ADR-004 skip side effect: REQUIRED PENDING → MISSED in same transaction."""
    result = await db.execute(
        select(MeasurementRequirement).where(
            MeasurementRequirement.brew_session_id == session.id,
            MeasurementRequirement.stage_occurrence_id == stage.id,
            MeasurementRequirement.status == MeasurementRequirementStatus.PENDING,
            MeasurementRequirement.requirement_level == MeasurementRequirementLevel.REQUIRED,
        )
    )
    for req in result.scalars().all():
        await _append_status(
            db,
            requirement=req,
            from_status=MeasurementRequirementStatus.PENDING,
            to_status=MeasurementRequirementStatus.MISSED,
            actor_id=actor_id,
            source_command="SKIP_STAGE",
            reason=f"Auto-MISSED because stage {stage.stage_code} was skipped",
            client_submission_id=client_submission_id,
            client_occurred_at=client_occurred_at,
            payload={"stage_code": stage.stage_code, "skip_reason": stage.skip_reason},
        )
        await brew_events_service.append_brew_event(
            db,
            brewery_id=session.brewery_id,
            brew_plan_id=session.brew_plan_id,
            brew_session_id=session.id,
            event_type=BrewEventType.MEASUREMENT_MISSED,
            actor_id=actor_id,
            payload={
                "requirement_id": req.id,
                "measurement_code": req.measurement_code,
                "source": "SKIP_STAGE",
                "stage_code": stage.stage_code,
            },
            client_submission_id=client_submission_id,
            client_occurred_at=client_occurred_at,
        )


async def pending_required_blocks_close(db: AsyncSession, session_id: str) -> list[str]:
    result = await db.execute(
        select(MeasurementRequirement.measurement_code).where(
            MeasurementRequirement.brew_session_id == session_id,
            MeasurementRequirement.requirement_level == MeasurementRequirementLevel.REQUIRED,
            MeasurementRequirement.status == MeasurementRequirementStatus.PENDING,
        )
    )
    return list(result.scalars().all())
