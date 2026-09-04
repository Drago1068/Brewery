"""Yeast provenance and pitch history (§11).

Implements P4-FR-066 (optional same-owner lot linkage + immutable snapshot),
P4-FR-067 (source-pair agreement/ownership/temporal/aborted rules),
P4-FR-068 (pitch history by session/lot/owner from snapshots), and
P4-FR-069 (circular-lineage rejection under transactional locking).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.application.events import audit
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.domain.fermentation.constants import YEAST_SOURCE_FINISHING_STATUSES
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationSession,
    FermentationYeastPitchReference,
    FermentationYeastReferenceHistory,
)
from brewing_api.domain.identity.models import User
from brewing_api.domain.ingredients.models import Ingredient, IngredientLot
from brewing_api.platform.time import utc_now


@dataclass(frozen=True)
class YeastEnrichCommand:
    operation_id: str
    expected_revision: int | None = None
    ingredient_lot_id: uuid.UUID | None = None
    preparation_method_note: str | None = None
    pitch_inputs: dict | None = None
    field_provenance: dict | None = None
    declaration_note: str | None = None
    source_fermentation_session_id: uuid.UUID | None = None
    source_yeast_reference_id: uuid.UUID | None = None
    reason: str | None = None


def _lock_session(db: Session, user: User, session_id: uuid.UUID) -> FermentationSession:
    session = db.scalar(
        select(FermentationSession)
        .where(FermentationSession.id == session_id, FermentationSession.user_id == user.id)
        .with_for_update()
    )
    if session is None:
        raise DomainError("Fermentation session not found", 404)
    return session


def _get_reference(
    db: Session, fermentation_session_id: uuid.UUID
) -> FermentationYeastPitchReference:
    ref = db.scalar(
        select(FermentationYeastPitchReference).where(
            FermentationYeastPitchReference.fermentation_session_id == fermentation_session_id
        )
    )
    if ref is None:
        raise ConflictError("Yeast reference has not been declared", code="YEAST_REFERENCE_MISSING")
    return ref


def _lock_reference(db: Session, reference_id: uuid.UUID) -> FermentationYeastPitchReference | None:
    return db.scalar(
        select(FermentationYeastPitchReference)
        .where(FermentationYeastPitchReference.id == reference_id)
        .with_for_update()
    )


def _lock_references_in_id_order(
    db: Session, reference_ids: set[uuid.UUID]
) -> dict[uuid.UUID, FermentationYeastPitchReference]:
    locked: dict[uuid.UUID, FermentationYeastPitchReference] = {}
    for reference_id in sorted(reference_ids):
        ref = _lock_reference(db, reference_id)
        if ref is not None:
            locked[reference_id] = ref
    return locked


def _build_lot_snapshot(db: Session, lot: IngredientLot) -> dict:
    ingredient = db.get(Ingredient, lot.ingredient_id)
    attributes = dict(ingredient.attributes or {}) if ingredient is not None else {}
    return {
        "lot_code": lot.lot_code,
        "manufacturer": ingredient.manufacturer if ingredient is not None else None,
        "product": ingredient.name if ingredient is not None else None,
        "form": ingredient.category if ingredient is not None else None,
        "strain": attributes.get("strain"),
        "generation_label": (
            attributes.get("generation_label")
            or attributes.get("generation-label")
            or attributes.get("generation")
        ),
        "attributes": attributes,
        "unit": lot.unit,
    }


def _snapshot(reference: FermentationYeastPitchReference) -> dict:
    return {
        "ingredient_lot_id": (
            str(reference.ingredient_lot_id) if reference.ingredient_lot_id else None
        ),
        "lot_snapshot": dict(reference.lot_snapshot or {}),
        "preparation_method_note": reference.preparation_method_note,
        "pitch_inputs": dict(reference.pitch_inputs or {}),
        "field_provenance": dict(reference.field_provenance or {}),
        "source_fermentation_session_id": (
            str(reference.source_fermentation_session_id)
            if reference.source_fermentation_session_id
            else None
        ),
        "source_yeast_reference_id": (
            str(reference.source_yeast_reference_id)
            if reference.source_yeast_reference_id
            else None
        ),
        "declaration_note": reference.declaration_note,
    }


def _lineage_reaches(db: Session, start_id: uuid.UUID, target_id: uuid.UUID) -> bool:
    seen: set[uuid.UUID] = set()
    current_id: uuid.UUID | None = start_id
    while current_id is not None and current_id not in seen:
        if current_id == target_id:
            return True
        seen.add(current_id)
        ref = db.get(FermentationYeastPitchReference, current_id)
        if ref is None or ref.source_yeast_reference_id is None:
            return False
        current_id = ref.source_yeast_reference_id
    return False


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


def _document(command: YeastEnrichCommand) -> dict:
    return {
        "command_name": "EnrichYeastReference",
        "expected_revision": command.expected_revision,
        "ingredient_lot_id": str(command.ingredient_lot_id) if command.ingredient_lot_id else None,
        "preparation_method_note": command.preparation_method_note,
        "pitch_inputs": command.pitch_inputs or {},
        "field_provenance": command.field_provenance or {},
        "declaration_note": command.declaration_note,
        "source_fermentation_session_id": (
            str(command.source_fermentation_session_id)
            if command.source_fermentation_session_id
            else None
        ),
        "source_yeast_reference_id": (
            str(command.source_yeast_reference_id) if command.source_yeast_reference_id else None
        ),
        "reason": command.reason,
    }


def _validate_source_pair(
    db: Session,
    user: User,
    current_ref: FermentationYeastPitchReference,
    command: YeastEnrichCommand,
) -> FermentationYeastPitchReference:
    has_session = command.source_fermentation_session_id is not None
    has_reference = command.source_yeast_reference_id is not None
    if has_session != has_reference:
        raise DomainError(
            "Yeast reuse source pair must be both set or both unset",
            422,
            code="SOURCE_PAIR_INCOMPLETE",
        )
    if not has_session:
        return current_ref

    source_session = db.get(FermentationSession, command.source_fermentation_session_id)  # type: ignore[arg-type]
    if source_session is None or source_session.user_id != user.id:
        raise DomainError("Source fermentation session not found", 404)

    source_ref = db.get(FermentationYeastPitchReference, command.source_yeast_reference_id)  # type: ignore[arg-type]
    if source_ref is None or source_ref.fermentation_session_id != source_session.id:
        raise DomainError(
            "Source yeast reference does not belong to the source session",
            422,
            code="SOURCE_PAIR_MISMATCH",
        )

    if source_ref.id == current_ref.id:
        raise DomainError("Yeast lineage cycle is not permitted", 422, code="YEAST_LINEAGE_CYCLE")

    if source_session.status == "ABORTED":
        raise DomainError(
            "Yeast cannot be reused from an aborted session", 422, code="SOURCE_SESSION_ABORTED"
        )
    if source_session.status not in YEAST_SOURCE_FINISHING_STATUSES:
        raise DomainError(
            "Yeast can only be reused from a finished or finishing fermentation session",
            422,
            code="SOURCE_SESSION_NOT_FINISHED",
        )

    if source_ref.pitched_at is None or current_ref.pitched_at is None:
        raise DomainError(
            "Yeast pitch timestamps are unavailable for temporal comparison",
            422,
            code="SOURCE_TEMPORAL_INVALID",
        )
    if source_ref.pitched_at >= current_ref.pitched_at:
        raise DomainError(
            "Yeast source must have been pitched before the current session",
            422,
            code="SOURCE_TEMPORAL_INVALID",
        )

    return source_ref


def enrich_yeast_reference(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: YeastEnrichCommand,
) -> FermentationYeastPitchReference:
    get_fermentation_session(db, user, session_id)
    replay = replay_or_conflict(
        db,
        user.id,
        "EnrichYeastReference",
        "FermentationSession",
        session_id,
        command.operation_id,
        _document(command),
    )
    current_ref = _get_reference(db, session_id)
    if replay and replay.result_resource_id:
        found = db.get(FermentationYeastPitchReference, replay.result_resource_id)
        if found is not None:
            return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")

    terminal = session.status in {"CLOSED", "ABORTED"}
    if terminal:
        _apply_terminal_annotation(db, user, session, current_ref, command)
        _persist_enrichment(db, user, session, current_ref, command, kind="ANNOTATE")
        db.commit()
        db.refresh(current_ref)
        return current_ref

    prior = _snapshot(current_ref)

    if command.ingredient_lot_id is not None:
        lot = db.get(IngredientLot, command.ingredient_lot_id)
        if lot is None or lot.owner_id != user.id:
            raise DomainError("Yeast ingredient lot not found", 404)
        current_ref.ingredient_lot_id = lot.id
        current_ref.lot_snapshot = _build_lot_snapshot(db, lot)

    if command.preparation_method_note is not None:
        current_ref.preparation_method_note = command.preparation_method_note
    if command.pitch_inputs is not None:
        current_ref.pitch_inputs = dict(command.pitch_inputs)
    if command.field_provenance is not None:
        current_ref.field_provenance = dict(command.field_provenance)
    if command.declaration_note is not None:
        current_ref.declaration_note = command.declaration_note

    if (
        command.source_fermentation_session_id is not None
        or command.source_yeast_reference_id is not None
    ):
        source_ref = _validate_source_pair(db, user, current_ref, command)
        _lock_references_in_id_order(db, {current_ref.id, source_ref.id})
        if _lineage_reaches(db, source_ref.id, current_ref.id):
            raise ConflictError("Yeast lineage cycle conflict", code="YEAST_LINEAGE_CYCLE")
        current_ref.source_fermentation_session_id = command.source_fermentation_session_id
        current_ref.source_yeast_reference_id = command.source_yeast_reference_id
    else:
        current_ref.source_fermentation_session_id = None
        current_ref.source_yeast_reference_id = None

    _persist_enrichment(db, user, session, current_ref, command, prior=prior, kind="ENRICH")
    db.commit()
    db.refresh(current_ref)
    return current_ref


def _apply_terminal_annotation(
    db: Session,
    user: User,
    session: FermentationSession,
    current_ref: FermentationYeastPitchReference,
    command: YeastEnrichCommand,
) -> None:
    source_pair_or_lot = (
        command.source_fermentation_session_id is not None
        or command.source_yeast_reference_id is not None
        or command.ingredient_lot_id is not None
    )
    if source_pair_or_lot:
        raise ConflictError(
            "Yeast source pair and lot are immutable at terminal state",
            code="YEAST_TERMINAL_MUTATION_DENIED",
        )
    terminal_at = session.closed_at or session.aborted_at
    if terminal_at is not None and utc_now() > terminal_at + timedelta(days=7):
        raise ConflictError(
            "Yeast annotation window has closed", code="YEAST_ANNOTATION_WINDOW_CLOSED"
        )
    if command.declaration_note is not None:
        current_ref.declaration_note = command.declaration_note


def _persist_enrichment(
    db: Session,
    user: User,
    session: FermentationSession,
    current_ref: FermentationYeastPitchReference,
    command: YeastEnrichCommand,
    *,
    prior: dict | None = None,
    kind: str,
) -> None:
    prior = prior if prior is not None else _snapshot(current_ref)
    new = _snapshot(current_ref)
    now = utc_now()
    current_ref.actor_user_id = user.id
    current_ref.enriched_at = now
    current_ref.revision += 1

    db.add(
        FermentationYeastReferenceHistory(
            fermentation_yeast_reference_id=current_ref.id,
            fermentation_session_id=session.id,
            kind=kind,
            prior_snapshot=prior,
            new_snapshot=new,
            actor_user_id=user.id,
            operation_id=command.operation_id,
            reason=command.reason,
            recorded_at=now,
        )
    )

    is_first_declaration = current_ref.revision == 1
    event_type = "YEAST_REFERENCE_RECORDED" if is_first_declaration else "YEAST_REFERENCE_CORRECTED"
    _journal(
        db,
        session.id,
        event_type,
        "Yeast provenance declaration recorded or corrected",
        actor_id=user.id,
        operation_id=command.operation_id,
    )
    audit(
        db, user.id, "YEAST_REFERENCE_ENRICHED", "FermentationYeastPitchReference", current_ref.id
    )

    session.revision += 1
    store_success(
        db,
        user.id,
        "EnrichYeastReference",
        "FermentationSession",
        session.id,
        command.operation_id,
        _document(command),
        {"id": str(current_ref.id), "revision": current_ref.revision},
        "FermentationYeastPitchReference",
        current_ref.id,
    )


def serialize_yeast_reference(reference: FermentationYeastPitchReference | None) -> dict | None:
    if reference is None:
        return None
    return {
        "id": str(reference.id),
        "fermentation_session_id": str(reference.fermentation_session_id),
        "brew_pitch_handoff_id": str(reference.brew_pitch_handoff_id),
        "yeast_note": reference.yeast_note,
        "pitch_temperature_c": (
            None if reference.pitch_temperature_c is None else str(reference.pitch_temperature_c)
        ),
        "pitched_at": reference.pitched_at,
        "schema_version": reference.schema_version,
        "ingredient_lot_id": (
            str(reference.ingredient_lot_id) if reference.ingredient_lot_id else None
        ),
        "lot_snapshot": dict(reference.lot_snapshot or {}),
        "preparation_method_note": reference.preparation_method_note,
        "pitch_inputs": dict(reference.pitch_inputs or {}),
        "field_provenance": dict(reference.field_provenance or {}),
        "source_fermentation_session_id": (
            str(reference.source_fermentation_session_id)
            if reference.source_fermentation_session_id
            else None
        ),
        "source_yeast_reference_id": (
            str(reference.source_yeast_reference_id)
            if reference.source_yeast_reference_id
            else None
        ),
        "declaration_note": reference.declaration_note,
        "revision": reference.revision,
    }


def pitch_history(
    db: Session,
    user: User,
    *,
    session_id: uuid.UUID | None = None,
    lot_id: uuid.UUID | None = None,
) -> list[dict]:
    if session_id is not None:
        owned_session = db.get(FermentationSession, session_id)
        if owned_session is None or owned_session.user_id != user.id:
            raise DomainError("Fermentation session not found", 404)

    query = (
        select(FermentationYeastPitchReference)
        .join(
            FermentationSession,
            FermentationSession.id == FermentationYeastPitchReference.fermentation_session_id,
        )
        .where(FermentationSession.user_id == user.id)
        .order_by(FermentationYeastPitchReference.created_at)
    )
    if session_id is not None:
        query = query.where(FermentationYeastPitchReference.fermentation_session_id == session_id)
    if lot_id is not None:
        query = query.where(FermentationYeastPitchReference.ingredient_lot_id == lot_id)

    references = list(db.scalars(query).all())
    return [serialize_yeast_reference(reference) for reference in references]  # type: ignore[misc]
