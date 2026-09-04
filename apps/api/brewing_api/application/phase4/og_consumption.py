"""Phase 4 original-gravity consumption (`phase4-og-consumption-v1`)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.application.events import audit
from brewing_api.application.phase4.completion import invalidate_after_fermentation_affecting_evidence
from brewing_api.application.phase4.derived_gravity import recompute_derived_gravity
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationOgConsumption,
    FermentationSession,
)
from brewing_api.domain.identity.models import User
from brewing_api.domain.measurements.models import Measurement
from brewing_api.platform.time import utc_now


@dataclass(frozen=True)
class ReconcileOgCommand:
    operation_id: str
    brew_measurement_id: uuid.UUID
    expected_revision: int | None = None


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
    db: Session, brew_session_id: uuid.UUID, *, required: bool = False
) -> Measurement | None:
    """Return the current brew-side OG leaf, or None when genuinely absent (§6.2.1)."""
    leaf = current_original_gravity_leaf(db, brew_session_id)
    if leaf is None and required:
        raise DomainError(
            "Current effective ORIGINAL_GRAVITY leaf is required",
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


def current_og_consumption(
    db: Session, fermentation_session_id: uuid.UUID
) -> FermentationOgConsumption | None:
    return db.scalar(
        select(FermentationOgConsumption).where(
            FermentationOgConsumption.fermentation_session_id == fermentation_session_id,
            FermentationOgConsumption.is_current.is_(True),
        )
    )


def _correction_id_for_leaf(db: Session, leaf: Measurement) -> uuid.UUID | None:
    """If the effective leaf is a correction row, return its id; else None."""
    if leaf.correction_of_id is None:
        return None
    return leaf.id


def _canonical_sg(leaf: Measurement) -> Decimal:
    if leaf.canonical_value is not None:
        return leaf.canonical_value
    return leaf.value


def _canonical_unit(leaf: Measurement) -> str:
    if leaf.canonical_unit:
        return leaf.canonical_unit
    return leaf.unit


def pin_og_at_start(
    db: Session,
    *,
    fermentation_session_id: uuid.UUID,
    leaf: Measurement | None,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> FermentationOgConsumption:
    """Persist the start-transaction OG pin: KNOWN leaf or UNKNOWN (§6.2.1 steps 1–3)."""
    now = utc_now()
    if leaf is None:
        row = FermentationOgConsumption(
            fermentation_session_id=fermentation_session_id,
            brew_measurement_id=None,
            brew_correction_id=None,
            consumed_value=None,
            consumed_unit=None,
            og_availability="UNKNOWN",
            is_current=True,
            pin_ordinal=1,
            og_observed_at=None,
            actor_user_id=actor_id,
            operation_id=operation_id,
            consumed_at=now,
        )
    else:
        row = FermentationOgConsumption(
            fermentation_session_id=fermentation_session_id,
            brew_measurement_id=leaf.id,
            brew_correction_id=_correction_id_for_leaf(db, leaf),
            consumed_value=_canonical_sg(leaf),
            consumed_unit=_canonical_unit(leaf),
            og_availability="KNOWN",
            is_current=True,
            pin_ordinal=1,
            og_observed_at=leaf.measured_at,
            actor_user_id=actor_id,
            operation_id=operation_id,
            consumed_at=now,
        )
    db.add(row)
    db.flush()
    return row


def serialize_og_consumption(row: FermentationOgConsumption | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "og_availability": row.og_availability,
        "is_current": row.is_current,
        "pin_ordinal": row.pin_ordinal,
        "brew_measurement_id": None
        if row.brew_measurement_id is None
        else str(row.brew_measurement_id),
        "brew_correction_id": None
        if row.brew_correction_id is None
        else str(row.brew_correction_id),
        "consumed_value": None if row.consumed_value is None else str(row.consumed_value),
        "consumed_unit": row.consumed_unit,
        "og_observed_at": row.og_observed_at,
        "consumed_at": row.consumed_at,
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
    event_data: dict | None = None,
) -> None:
    now = utc_now()
    db.add(
        FermentationJournalEvent(
            fermentation_session_id=session_id,
            event_type=event_type,
            message=message,
            event_data=event_data or {},
            occurred_at=now,
            recorded_at=now,
            actor_user_id=actor_id,
            operation_id=operation_id,
        )
    )


def _lock_session(db: Session, user: User, session_id: uuid.UUID) -> FermentationSession:
    session = (
        db.execute(
            select(FermentationSession)
            .where(FermentationSession.id == session_id)
            .with_for_update()
        )
        .scalar_one_or_none()
    )
    if session is None or session.user_id != user.id:
        raise DomainError("Fermentation session not found", 404)
    return session


def _resolve_leaf_for_reconcile(
    db: Session,
    user: User,
    session: FermentationSession,
    brew_measurement_id: uuid.UUID,
) -> Measurement:
    from brewing_api.domain.brew_sessions.models import BrewSession

    measurement = db.get(Measurement, brew_measurement_id)
    if measurement is None:
        raise DomainError("Original gravity measurement not found", 404)
    brew_session = db.get(BrewSession, session.brew_session_id)
    if brew_session is None or brew_session.user_id != user.id:
        raise DomainError("Original gravity measurement not found", 404)
    if measurement.brew_session_id != session.brew_session_id:
        raise DomainError("Original gravity measurement not found", 404)
    if measurement.measurement_type != "ORIGINAL_GRAVITY":
        raise DomainError(
            "Only ORIGINAL_GRAVITY leaves may be reconciled as OG",
            422,
            code="INVALID_OG_SOURCE",
        )

    # Walk to the chain root, then to the current leaf.
    chain_root = measurement
    while chain_root.correction_of_id is not None:
        parent = db.get(Measurement, chain_root.correction_of_id)
        if parent is None:
            break
        chain_root = parent
    leaf = _follow_correction_chain(db, chain_root)

    current_leaf = current_original_gravity_leaf(db, session.brew_session_id)
    if current_leaf is None:
        raise DomainError(
            "No current ORIGINAL_GRAVITY leaf available to reconcile",
            422,
            code="ORIGINAL_GRAVITY_REQUIRED",
        )
    if leaf.id != current_leaf.id:
        raise DomainError(
            "Cited measurement is not the current ORIGINAL_GRAVITY leaf for this brew",
            422,
            code="STALE_OG_LEAF",
        )
    return current_leaf


def reconcile_upstream_original_gravity(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: ReconcileOgCommand,
) -> FermentationOgConsumption:
    """Append a new OG pin from a later Phase 3 leaf without rewriting history (§6.2.1)."""
    get_fermentation_session(db, user, session_id)
    document = {
        "command_name": "ReconcileUpstreamOriginalGravity",
        "fermentation_session_id": str(session_id),
        "brew_measurement_id": str(command.brew_measurement_id),
        "expected_revision": command.expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "ReconcileUpstreamOriginalGravity",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationOgConsumption, replay.result_resource_id)
        if found is not None:
            return found

    session = _lock_session(db, user, session_id)
    if session.status in {"CLOSED", "ABORTED"}:
        raise ConflictError(
            "OG reconciliation is not allowed on CLOSED or ABORTED sessions",
            code="INVALID_TRANSITION",
        )
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")

    leaf = _resolve_leaf_for_reconcile(db, user, session, command.brew_measurement_id)
    prior = current_og_consumption(db, session.id)
    prior_sg = prior.consumed_value if prior is not None else None
    new_sg = _canonical_sg(leaf)

    if (
        prior is not None
        and prior.og_availability == "KNOWN"
        and prior.brew_measurement_id == leaf.id
        and prior.consumed_value == new_sg
    ):
        # Same authoritative leaf already current — treat as no-op success for retries
        # without a stored operation (still store success below via normal path when op given).
        store_success(
            db,
            user.id,
            "ReconcileUpstreamOriginalGravity",
            "FermentationSession",
            session.id,
            command.operation_id,
            document,
            {"id": str(prior.id), "og_availability": prior.og_availability},
            "FermentationOgConsumption",
            prior.id,
        )
        db.commit()
        db.refresh(prior)
        return prior

    now = utc_now()
    next_ordinal = 1 if prior is None else prior.pin_ordinal + 1
    if prior is not None:
        prior.is_current = False

    row = FermentationOgConsumption(
        fermentation_session_id=session.id,
        brew_measurement_id=leaf.id,
        brew_correction_id=_correction_id_for_leaf(db, leaf),
        consumed_value=new_sg,
        consumed_unit=_canonical_unit(leaf),
        og_availability="KNOWN",
        is_current=True,
        pin_ordinal=next_ordinal,
        og_observed_at=leaf.measured_at,
        actor_user_id=user.id,
        operation_id=command.operation_id,
        consumed_at=now,
    )
    db.add(row)
    db.flush()

    session.revision += 1
    sg_changed = prior_sg is None or prior_sg != new_sg
    if sg_changed:
        invalidate_after_fermentation_affecting_evidence(
            db, session, cause_id=row.id, actor_id=user.id
        )
    recompute_derived_gravity(db, session.id)

    _journal(
        db,
        session.id,
        "ORIGINAL_GRAVITY_RECONCILED",
        "Upstream original gravity reconciled",
        actor_id=user.id,
        operation_id=command.operation_id,
        event_data={
            "og_consumption_id": str(row.id),
            "brew_measurement_id": str(leaf.id),
            "prior_og_consumption_id": None if prior is None else str(prior.id),
            "prior_availability": None if prior is None else prior.og_availability,
            "consumed_value": str(new_sg),
            "completion_affecting": sg_changed,
        },
    )
    audit(db, user.id, "ORIGINAL_GRAVITY_RECONCILED", "FermentationOgConsumption", row.id)
    store_success(
        db,
        user.id,
        "ReconcileUpstreamOriginalGravity",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        {
            "id": str(row.id),
            "og_availability": row.og_availability,
            "brew_measurement_id": str(leaf.id),
            "pin_ordinal": row.pin_ordinal,
        },
        "FermentationOgConsumption",
        row.id,
    )
    db.commit()
    db.refresh(row)
    return row
