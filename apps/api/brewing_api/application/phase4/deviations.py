"""Phase 4 derived deviations (§22 / P4-FR-058)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.domain.fermentation.constants import DEVIATION_SCHEMA_VERSION
from brewing_api.domain.fermentation.models import (
    FermentationDeviation,
    FermentationJournalEvent,
    FermentationMeasurement,
    FermentationPlanSnapshot,
    FermentationSession,
    FermentationYeastPitchReference,
)
from brewing_api.platform.time import utc_now

DERIVED_DEVIATION_NAMESPACE = uuid.UUID("d81f0c2e-4a77-5b1d-9e08-3c55a91b7f10")


def derived_deviation_identity(
    *,
    session_id: uuid.UUID,
    deviation_class: str,
    source_evidence_id: uuid.UUID,
    plan_hash: str,
) -> uuid.UUID:
    return uuid.uuid5(
        DERIVED_DEVIATION_NAMESPACE,
        f"phase4-deviation-v1:{session_id}:{deviation_class}:{source_evidence_id}:{plan_hash}",
    )


def serialize_deviation(row: FermentationDeviation) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "deviation_class": row.deviation_class,
        "origin": row.origin,
        "derived_identity": None if row.derived_identity is None else str(row.derived_identity),
        "source_evidence_id": None
        if row.source_evidence_id is None
        else str(row.source_evidence_id),
        "plan_hash": row.plan_hash,
        "status": row.status,
        "exceeded": row.exceeded,
        "measured_value": None if row.measured_value is None else str(row.measured_value),
        "target_value": None if row.target_value is None else str(row.target_value),
        "tolerance_value": None if row.tolerance_value is None else str(row.tolerance_value),
        "variance": None if row.variance is None else str(row.variance),
        "unit": row.unit,
        "comparison_payload": row.comparison_payload or {},
        "resolution_note": row.resolution_note,
        "supersedes_id": None if row.supersedes_id is None else str(row.supersedes_id),
        "occurred_at": row.occurred_at,
        "recorded_at": row.recorded_at,
        "schema_version": row.schema_version,
    }


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


def _current_leaf(
    db: Session,
    session_id: uuid.UUID,
    deviation_class: str,
    source_evidence_id: uuid.UUID,
) -> FermentationDeviation | None:
    return db.scalar(
        select(FermentationDeviation).where(
            FermentationDeviation.fermentation_session_id == session_id,
            FermentationDeviation.deviation_class == deviation_class,
            FermentationDeviation.source_evidence_id == source_evidence_id,
            FermentationDeviation.status == "CURRENT",
        )
    )


def _plan_and_pitch(
    db: Session, session: FermentationSession
) -> tuple[FermentationPlanSnapshot | None, FermentationYeastPitchReference | None]:
    snapshot = db.scalar(
        select(FermentationPlanSnapshot).where(
            FermentationPlanSnapshot.fermentation_session_id == session.id
        )
    )
    pitch = db.scalar(
        select(FermentationYeastPitchReference).where(
            FermentationYeastPitchReference.fermentation_session_id == session.id
        )
    )
    return snapshot, pitch


def temperature_target_at(
    snapshot: FermentationPlanSnapshot | None,
    *,
    pitched_at: datetime | None,
    observed_at: datetime,
    conditioning: bool = False,
) -> tuple[Decimal | None, Decimal, str]:
    """Return (target_c, tolerance_c, provenance) from plan snapshot at observed_at."""
    if snapshot is not None and isinstance(snapshot.payload, dict):
        payload = snapshot.payload
    else:
        payload = {}
    tolerance_raw = payload.get("temperature_tolerance_c", "1.0")
    tolerance = Decimal(str(tolerance_raw))
    provenance = str(
        payload.get("temperature_tolerance_provenance") or "PHASE4_DEFAULT_TOLERANCE_V1"
    )

    schedule_key = "conditioning_schedule" if conditioning else "schedule"
    schedule = payload.get(schedule_key)
    single_key = "conditioning_temperature_c" if conditioning else "fermentation_temperature_c"
    status_key = "fermentation_temperature_status"

    if isinstance(schedule, list) and schedule and pitched_at is not None:
        from brewing_api.application.phase4.time_validation import _coerce_aware

        elapsed = _coerce_aware(observed_at) - _coerce_aware(pitched_at)
        elapsed_minutes = int(elapsed.total_seconds() // 60)
        ordered = sorted(
            (
                item
                for item in schedule
                if isinstance(item, dict) and "effective_offset_minutes" in item
            ),
            key=lambda item: int(item["effective_offset_minutes"]),
        )
        active: Decimal | None = None
        for item in ordered:
            offset = int(item["effective_offset_minutes"])
            if offset <= elapsed_minutes:
                active = Decimal(str(item["target_temp_c"]))
            else:
                break
        if active is not None:
            return active, tolerance, provenance

    if conditioning:
        raw = payload.get(single_key)
        if raw is None:
            return None, tolerance, provenance
        return Decimal(str(raw)), tolerance, provenance

    if payload.get(status_key) == "UNSPECIFIED" or payload.get(single_key) is None:
        return None, tolerance, provenance
    return Decimal(str(payload[single_key])), tolerance, provenance


def append_derived_deviation(
    db: Session,
    session: FermentationSession,
    *,
    deviation_class: str,
    source_evidence_id: uuid.UUID,
    occurred_at: datetime,
    exceeded: bool,
    measured_value: Decimal | None = None,
    target_value: Decimal | None = None,
    tolerance_value: Decimal | None = None,
    unit: str | None = None,
    comparison_payload: dict | None = None,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> FermentationDeviation | None:
    """Append CURRENT derived leaf; supersede prior CURRENT for same source key."""
    plan_hash = session.logical_plan_hash or ""
    identity = derived_deviation_identity(
        session_id=session.id,
        deviation_class=deviation_class,
        source_evidence_id=source_evidence_id,
        plan_hash=plan_hash,
    )
    prior = _current_leaf(db, session.id, deviation_class, source_evidence_id)
    if prior is not None:
        # No-op when comparison state is unchanged.
        same = (
            prior.exceeded == exceeded
            and prior.measured_value == measured_value
            and prior.target_value == target_value
            and prior.tolerance_value == tolerance_value
        )
        if same:
            return prior
        prior.status = "SUPERSEDED"
        _journal(
            db,
            session.id,
            "FERMENTATION_DEVIATION_SUPERSEDED",
            f"{deviation_class} superseded",
            actor_id=actor_id,
            operation_id=operation_id,
            occurred_at=occurred_at,
            event_data={
                "deviation_id": str(prior.id),
                "derived_identity": str(identity),
                "source_evidence_id": str(source_evidence_id),
            },
        )

    # First observation within tolerance with no prior leaf: nothing to record.
    if prior is None and not exceeded:
        return None

    variance = None
    if measured_value is not None and target_value is not None:
        variance = abs(measured_value - target_value)

    now = utc_now()
    row = FermentationDeviation(
        fermentation_session_id=session.id,
        deviation_class=deviation_class,
        origin="DERIVED",
        derived_identity=identity,
        source_evidence_id=source_evidence_id,
        plan_hash=plan_hash,
        status="CURRENT",
        exceeded=exceeded,
        measured_value=measured_value,
        target_value=target_value,
        tolerance_value=tolerance_value,
        variance=variance,
        unit=unit,
        comparison_payload=comparison_payload or {},
        supersedes_id=None if prior is None else prior.id,
        occurred_at=occurred_at,
        recorded_at=now,
        actor_user_id=actor_id,
        operation_id=operation_id,
        schema_version=DEVIATION_SCHEMA_VERSION,
    )
    db.add(row)
    db.flush()
    _journal(
        db,
        session.id,
        "FERMENTATION_DEVIATION_RECORDED",
        f"{deviation_class} recorded",
        actor_id=actor_id,
        operation_id=operation_id,
        occurred_at=occurred_at,
        event_data={
            "deviation_id": str(row.id),
            "derived_identity": str(identity),
            "source_evidence_id": str(source_evidence_id),
            "exceeded": exceeded,
            "supersedes_id": None if prior is None else str(prior.id),
        },
    )
    return row


def evaluate_temperature_excursion(
    db: Session,
    session: FermentationSession,
    measurement: FermentationMeasurement,
    *,
    measured_value: Decimal,
    observed_at: datetime,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> FermentationDeviation | None:
    if measurement.measurement_type not in {
        "FERMENTATION_TEMPERATURE",
        "CONDITIONING_TEMPERATURE",
    }:
        return None
    snapshot, pitch = _plan_and_pitch(db, session)
    conditioning = measurement.measurement_type == "CONDITIONING_TEMPERATURE"
    pitched_at = None if pitch is None else pitch.pitched_at
    if conditioning and session.conditioning_first_started_at is not None:
        # §10.2 conditioning_schedule anchored at conditioning_first_started_at
        pitched_at = session.conditioning_first_started_at
    target, tolerance, provenance = temperature_target_at(
        snapshot,
        pitched_at=pitched_at,
        observed_at=observed_at,
        conditioning=conditioning,
    )
    if target is None:
        return None
    variance = abs(measured_value - target)
    exceeded = variance > tolerance
    return append_derived_deviation(
        db,
        session,
        deviation_class="TEMPERATURE_EXCURSION",
        source_evidence_id=measurement.id,
        occurred_at=observed_at,
        exceeded=exceeded,
        measured_value=measured_value,
        target_value=target,
        tolerance_value=tolerance,
        unit="degC",
        comparison_payload={
            "measurement_type": measurement.measurement_type,
            "tolerance_provenance": provenance,
        },
        actor_id=actor_id,
        operation_id=operation_id,
    )


def evaluate_stable_gravity_broken(
    db: Session,
    session: FermentationSession,
    *,
    source_measurement_id: uuid.UUID,
    prior_status: str | None,
    new_status: str,
    occurred_at: datetime,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> FermentationDeviation | None:
    if prior_status != "STABLE" or new_status == "STABLE":
        return None
    return append_derived_deviation(
        db,
        session,
        deviation_class="STABLE_GRAVITY_BROKEN",
        source_evidence_id=source_measurement_id,
        occurred_at=occurred_at,
        exceeded=True,
        comparison_payload={"prior_status": prior_status, "new_status": new_status},
        actor_id=actor_id,
        operation_id=operation_id,
    )


def list_session_deviations(db: Session, session_id: uuid.UUID) -> list[FermentationDeviation]:
    return list(
        db.scalars(
            select(FermentationDeviation)
            .where(FermentationDeviation.fermentation_session_id == session_id)
            .order_by(
                FermentationDeviation.occurred_at,
                FermentationDeviation.recorded_at,
                FermentationDeviation.id,
            )
        ).all()
    )
