from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.application.events import audit
from brewing_api.application.phase4.child_effects import materialize_start_children
from brewing_api.application.phase4.equipment import resolve_start_equipment
from brewing_api.application.phase4.og_consumption import (
    consume_original_gravity,
    pin_og_at_start,
)
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.plan import (
    MATERIALIZATION_RULE_VERSION,
    logical_plan_hash,
    materialize_phase4_plan,
    plan_preview_hash,
    plan_snapshot_payload,
    recipe_snapshot_payload,
)
from brewing_api.application.phase4.sessions import (
    get_active_fermentation_for_brew,
    get_owned_brew_session,
    require_pitch_handoff,
)
from brewing_api.domain.brew_sessions.models import BrewSession
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationPlanSnapshot,
    FermentationSession,
    FermentationStageInstance,
    FermentationYeastPitchReference,
)
from brewing_api.domain.identity.models import User
from brewing_api.domain.recipes.models import RecipeVersion
from brewing_api.platform.time import utc_now


def _journal(
    db: Session,
    session_id: uuid.UUID,
    event_type: str,
    message: str,
    *,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
    stage_id: uuid.UUID | None = None,
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
            occurred_at=now,
            recorded_at=now,
            actor_user_id=actor_id,
            operation_id=operation_id,
        )
    )


def start_fermentation_session(
    db: Session,
    user: User,
    brew_session_id: uuid.UUID,
    *,
    operation_id: str | None = None,
    expected_brew_revision: int | None = None,
    equipment_profile_id: uuid.UUID | None = None,
) -> FermentationSession:
    brew_session = get_owned_brew_session(db, user, brew_session_id)
    document = {
        "command_name": "StartFermentationSession",
        "brew_session_id": str(brew_session_id),
        "expected_brew_revision": expected_brew_revision,
        "equipment_profile_id": None if equipment_profile_id is None else str(equipment_profile_id),
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "StartFermentationSession",
        "BrewSession",
        brew_session.id,
        operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationSession, replay.result_resource_id)
        if found:
            return found

    if brew_session.status != "COMPLETED":
        raise DomainError(
            "Fermentation can only start from a completed brew session",
            409,
            code="BREW_SESSION_NOT_COMPLETED",
        )
    if expected_brew_revision is not None and brew_session.revision != expected_brew_revision:
        raise ConflictError("Brew session revision is stale", code="STALE_REVISION")

    # Serialize concurrent starts against the same brew session (PostgreSQL FOR UPDATE).
    locked_brew = db.scalar(
        select(BrewSession).where(BrewSession.id == brew_session.id).with_for_update()
    )
    assert locked_brew is not None
    brew_session = locked_brew

    existing = get_active_fermentation_for_brew(db, brew_session_id)
    if existing is not None:
        raise ConflictError(
            "An active fermentation session already exists for this brew session",
            code="FERMENTATION_SESSION_EXISTS",
            extra={"fermentation_session_id": str(existing.id)},
        )

    handoff = require_pitch_handoff(db, brew_session_id)
    og_leaf = consume_original_gravity(db, brew_session_id, required=False)
    now = utc_now()
    recipe_version = db.get(RecipeVersion, brew_session.recipe_version_id)
    if recipe_version is None:
        raise DomainError("Recipe version is missing for brew session", 409)

    logical_plan = materialize_phase4_plan(db, recipe_version)
    source_equipment_id, equipment_snapshot = resolve_start_equipment(
        db,
        user,
        recipe_version=recipe_version,
        equipment_profile_id=equipment_profile_id,
        snapshotted_at=now,
    )
    plan_hash = logical_plan_hash(logical_plan)
    preview_hash = plan_preview_hash(logical_plan)

    session = FermentationSession(
        user_id=user.id,
        brew_session_id=brew_session.id,
        brew_pitch_handoff_id=handoff.id,
        status="ACTIVE",
        revision=1,
        started_at=now,
        expected_brew_revision=expected_brew_revision or brew_session.revision,
        plan_kind=logical_plan.plan_kind,
        materialization_rule_version=MATERIALIZATION_RULE_VERSION,
        logical_plan_hash=plan_hash,
        plan_preview_hash=preview_hash,
        materialized_at=now,
        source_equipment_profile_id=source_equipment_id,
        equipment_snapshot=equipment_snapshot,
        conditioning_mode=logical_plan.conditioning_mode,
    )
    db.add(session)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "An active fermentation session already exists for this brew session",
            code="FERMENTATION_SESSION_EXISTS",
        ) from exc

    db.add(
        FermentationPlanSnapshot(
            fermentation_session_id=session.id,
            plan_kind=logical_plan.plan_kind,
            logical_plan_hash=plan_hash,
            preview_hash=preview_hash,
            payload=plan_snapshot_payload(
                logical_plan,
                recipe_snapshot=recipe_snapshot_payload(recipe_version),
            ),
        )
    )

    active_stage_id: uuid.UUID | None = None
    for step in logical_plan.steps:
        # §8.4: CONDITIONING and HANDOFF_READY rows are created by their commands, not at start.
        if step.canonical_stage_type not in {"PITCH_CONFIRMED", "ACTIVE_FERMENTATION"}:
            continue
        stage = FermentationStageInstance(
            fermentation_session_id=session.id,
            canonical_stage_type=step.canonical_stage_type,
            occurrence_number=step.occurrence_number,
            status="PENDING",
            plan_step_id=step.plan_step_id,
        )
        if step.canonical_stage_type == "PITCH_CONFIRMED":
            stage.status = "COMPLETED"
            stage.started_at = now
            stage.completed_at = now
        if step.canonical_stage_type == "ACTIVE_FERMENTATION":
            stage.status = "ACTIVE"
            stage.started_at = now
            stage.first_started_at = now
            stage.current_activation_started_at = now
        db.add(stage)
        db.flush()
        if step.canonical_stage_type == "ACTIVE_FERMENTATION":
            active_stage_id = stage.id

    assert active_stage_id is not None
    active_stage = db.get(FermentationStageInstance, active_stage_id)
    assert active_stage is not None
    materialize_start_children(
        db,
        session,
        active_stage,
        recipe_version_id=recipe_version.id,
        actor_id=user.id,
        operation_id=operation_id,
        pitched_at=handoff.pitched_at,
        additions=list(logical_plan.additions),
    )

    og_pin = pin_og_at_start(
        db,
        fermentation_session_id=session.id,
        leaf=og_leaf,
        actor_id=user.id,
        operation_id=operation_id,
    )
    db.add(
        FermentationYeastPitchReference(
            fermentation_session_id=session.id,
            brew_pitch_handoff_id=handoff.id,
            yeast_note=handoff.yeast_addition_note,
            pitch_temperature_c=handoff.pitch_temperature_c,
            pitched_at=handoff.pitched_at,
        )
    )

    _journal(
        db,
        session.id,
        "FERMENTATION_SESSION_STARTED",
        "Fermentation session started",
        actor_id=user.id,
        operation_id=operation_id,
        stage_id=active_stage_id,
        event_data={
            "brew_session_id": str(brew_session.id),
            "og_availability": og_pin.og_availability,
            "og_measurement_id": None if og_leaf is None else str(og_leaf.id),
            "pitch_handoff_id": str(handoff.id),
            "logical_plan_hash": plan_hash,
            "source_equipment_profile_id": None
            if source_equipment_id is None
            else str(source_equipment_id),
            "equipment_snapshotted": equipment_snapshot is not None,
        },
    )
    audit(db, user.id, "FERMENTATION_SESSION_STARTED", "FermentationSession", session.id)

    store_success(
        db,
        user.id,
        "StartFermentationSession",
        "BrewSession",
        brew_session.id,
        operation_id or "",
        document,
        {"id": str(session.id), "status": session.status},
        "FermentationSession",
        session.id,
        http_status=201,
    )
    db.commit()
    db.refresh(session)
    return session
