from __future__ import annotations

import uuid
from decimal import Decimal

from calculations.fermentation import (
    CALCULATION_UNDEFINED,
    GravityLeaf,
    STABLE_GRAVITY_SCHEMA_VERSION,
    final_gravity_from_leaves,
    stable_gravity_evaluator,
    try_abv_percent,
    try_apparent_attenuation_ratio,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.domain.fermentation.models import (
    FermentationDerivedGravitySnapshot,
    FermentationMeasurement,
    FermentationMeasurementCorrection,
    FermentationOgConsumption,
)
from brewing_api.platform.time import utc_now


def _effective_values(
    measurement: FermentationMeasurement,
    correction: FermentationMeasurementCorrection | None,
) -> tuple[Decimal, str, str | None]:
    if correction is None:
        return measurement.canonical_value, measurement.canonical_unit, measurement.conversion_model_id
    return correction.canonical_value, correction.canonical_unit, correction.conversion_model_id


def effective_measurement_leaf(
    db: Session, measurement: FermentationMeasurement
) -> tuple[FermentationMeasurement, FermentationMeasurementCorrection | None]:
    leaf_correction: FermentationMeasurementCorrection | None = None
    leaf_id = measurement.id
    while True:
        nxt = db.scalar(
            select(FermentationMeasurementCorrection).where(
                FermentationMeasurementCorrection.correction_of_id == leaf_id
            )
        )
        if nxt is None:
            return measurement, leaf_correction
        leaf_correction = nxt
        leaf_id = nxt.id


def effective_gravity_leaves(db: Session, session_id: uuid.UUID) -> list[GravityLeaf]:
    from brewing_api.application.phase4.time_validation import _coerce_aware

    measurements = list(
        db.scalars(
            select(FermentationMeasurement).where(
                FermentationMeasurement.fermentation_session_id == session_id,
                FermentationMeasurement.measurement_type == "FERMENTATION_GRAVITY",
                FermentationMeasurement.validation_status == "ACCEPTED",
            )
        ).all()
    )
    leaves: list[GravityLeaf] = []
    for measurement in measurements:
        _, correction = effective_measurement_leaf(db, measurement)
        canonical, _, _ = _effective_values(measurement, correction)
        observed_at = correction.observed_at if correction else measurement.observed_at
        recorded_at = correction.recorded_at if correction else measurement.recorded_at
        leaves.append(
            GravityLeaf(
                measurement_id=measurement.id,
                canonical_sg=canonical,
                observed_at=_coerce_aware(observed_at),
                recorded_at=_coerce_aware(recorded_at),
            )
        )
    return leaves


def recompute_derived_gravity(db: Session, session_id: uuid.UUID) -> FermentationDerivedGravitySnapshot:
    leaves = effective_gravity_leaves(db, session_id)
    evaluation = stable_gravity_evaluator(leaves)
    og_row = db.scalar(
        select(FermentationOgConsumption).where(
            FermentationOgConsumption.fermentation_session_id == session_id,
            FermentationOgConsumption.is_current.is_(True),
            FermentationOgConsumption.og_availability == "KNOWN",
        )
    )
    og = og_row.consumed_value if og_row is not None else None
    final_fg = final_gravity_from_leaves(leaves, evaluation)
    attenuation = (
        try_apparent_attenuation_ratio(og, final_fg)
        if final_fg is not None
        else CALCULATION_UNDEFINED
    )
    abv = (
        try_abv_percent(og, final_fg)
        if final_fg is not None
        else CALCULATION_UNDEFINED
    )
    snapshot = FermentationDerivedGravitySnapshot(
        fermentation_session_id=session_id,
        stable_gravity_status=evaluation.status.value,
        final_gravity_sg=final_fg,
        apparent_attenuation_ratio=None
        if attenuation == CALCULATION_UNDEFINED
        else attenuation,
        abv_percent=None if abv == CALCULATION_UNDEFINED else abv,
        spread=evaluation.spread,
        window_measurement_ids=[str(item) for item in evaluation.window_measurement_ids],
        source_measurement_ids=[str(item.measurement_id) for item in leaves],
        evaluated_at=utc_now(),
        calculation_version=STABLE_GRAVITY_SCHEMA_VERSION,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def latest_derived_gravity(
    db: Session, session_id: uuid.UUID
) -> FermentationDerivedGravitySnapshot | None:
    return db.scalar(
        select(FermentationDerivedGravitySnapshot)
        .where(FermentationDerivedGravitySnapshot.fermentation_session_id == session_id)
        .order_by(FermentationDerivedGravitySnapshot.evaluated_at.desc())
        .limit(1)
    )
