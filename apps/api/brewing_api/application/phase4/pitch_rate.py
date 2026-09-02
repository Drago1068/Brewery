from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from calculations.brewing import yeast_pitch_cells
from calculations.fermentation import NOT_COMPUTED
from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.domain.fermentation.models import (
    FermentationOgConsumption,
    FermentationPlanSnapshot,
    FermentationSession,
)
from brewing_api.domain.measurements.models import Measurement


def _follow_correction_chain(db: Session, root: Measurement) -> Measurement:
    leaf = root
    while True:
        successor = db.scalar(
            select(Measurement).where(Measurement.correction_of_id == leaf.id).limit(1)
        )
        if successor is None:
            return leaf
        leaf = successor


def current_knockout_volume_liters(db: Session, brew_session_id: uuid.UUID) -> Decimal | None:
    roots = list(
        db.scalars(
            select(Measurement).where(
                Measurement.brew_session_id == brew_session_id,
                Measurement.measurement_type == "KNOCKOUT_VOLUME",
                Measurement.correction_of_id.is_(None),
            )
        ).all()
    )
    if not roots:
        return None
    leaf = _follow_correction_chain(db, roots[0])
    if leaf.unit != "L":
        return None
    return leaf.value


def compute_pitch_rate_estimate(
    db: Session,
    session: FermentationSession,
    *,
    snapshot: FermentationPlanSnapshot | None,
    og: FermentationOgConsumption | None,
) -> dict[str, str]:
    recipe_snapshot = {}
    if snapshot is not None and isinstance(snapshot.payload, dict):
        raw = snapshot.payload.get("recipe_snapshot")
        if isinstance(raw, dict):
            recipe_snapshot = raw

    volume: Decimal | None = None
    batch_size = recipe_snapshot.get("batch_size_liters")
    if batch_size is not None:
        try:
            volume = Decimal(str(batch_size))
        except (InvalidOperation, ValueError):
            volume = None
    if volume is None:
        volume = current_knockout_volume_liters(db, session.brew_session_id)

    rate_raw = recipe_snapshot.get("pitch_rate_million_per_ml_plato")
    og_value = og.consumed_value if og is not None else None

    if volume is None or og_value is None or rate_raw is None:
        return {"status": NOT_COMPUTED}

    try:
        rate = Decimal(str(rate_raw))
        cells = yeast_pitch_cells(volume, og_value, rate)
    except (ValueError, InvalidOperation):
        return {"status": NOT_COMPUTED}

    return {
        "status": "CALCULATED",
        "provenance": "CALCULATED",
        "value": str(cells),
        "unit": "cells",
    }
