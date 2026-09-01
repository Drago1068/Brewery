from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import DomainError
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


def current_original_gravity_leaf(db: Session, brew_session_id: uuid.UUID) -> Measurement | None:
    roots = list(
        db.scalars(
            select(Measurement).where(
                Measurement.brew_session_id == brew_session_id,
                Measurement.measurement_type == "ORIGINAL_GRAVITY",
                Measurement.correction_of_id.is_(None),
            )
        ).all()
    )
    if not roots:
        return None
    if len(roots) > 1:
        raise DomainError(
            "Multiple root ORIGINAL_GRAVITY measurements found for brew session",
            409,
            code="AMBIGUOUS_ORIGINAL_GRAVITY",
        )
    return _follow_correction_chain(db, roots[0])


def consume_original_gravity(
    db: Session, brew_session_id: uuid.UUID, *, required: bool = True
) -> Measurement | None:
    leaf = current_original_gravity_leaf(db, brew_session_id)
    if leaf is None and required:
        raise DomainError(
            "Current effective ORIGINAL_GRAVITY leaf is required to start fermentation",
            422,
            code="ORIGINAL_GRAVITY_REQUIRED",
        )
    if leaf is not None and leaf.measurement_type != "ORIGINAL_GRAVITY":
        raise DomainError(
            "FERMENTATION_GRAVITY cannot be consumed as original gravity",
            422,
            code="INVALID_OG_SOURCE",
        )
    return leaf
