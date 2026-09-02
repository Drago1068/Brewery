from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from brewing_api.application.events import audit
from brewing_api.domain.recipes.models import RecipeVersion
from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.application.phase4.og_consumption import consume_original_gravity
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.plan import (
    MATERIALIZATION_RULE_VERSION,
    logical_plan_hash,
    materialize_default_plan,
    plan_preview_hash,
    plan_snapshot_payload,
    recipe_snapshot_payload,
)
from brewing_api.application.phase4.sessions import (
    get_active_fermentation_for_brew,
    get_owned_brew_session,
    require_pitch_handoff,
)
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationOgConsumption,
    FermentationPlanSnapshot,
    FermentationSession,
    FermentationStageInstance,
    FermentationYeastPitchReference,
)
from brewing_api.domain.identity.models import User
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
) -> FermentationSession:
    brew_session = get_owned_brew_session(db, user, brew_session_id)
    document = {
        "command_name": "StartFermentationSession",
        "brew_session_id": str(brew_session_id),
        "expected_brew_revision": expected_brew_revision,
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

    existing = get_active_fermentation_for_brew(db, brew_session_id)
    if existing is not None:
        raise ConflictError(
            "An active fermentation session already exists for this brew session",
            code="FERMENTATION_SESSION_EXISTS",
            extra={"fermentation_session_id": str(existing.id)},
        )

    handoff = require_pitch_handoff(db, brew_session_id)
    og_leaf = consume_original_gravity(db, brew_session_id, required=True)
    assert og_leaf is not None

    now = utc_now()
    logical_plan = materialize_default_plan(recipe_version_id=brew_session.recipe_version_id)
    recipe_version = db.get(RecipeVersion, brew_session.recipe_version_id)
    if recipe_version is None:
        raise DomainError("Recipe version is missing for brew session", 409)
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
        logical_plan_hash=logical_plan_hash(logical_plan),
        plan_preview_hash=plan_preview_hash(logical_plan),
        materialized_at=now,
    )
    db.add(session)
    db.flush()

    db.add(
        FermentationPlanSnapshot(
            fermentation_session_id=session.id,
            plan_kind=logical_plan.plan_kind,
            logical_plan_hash=logical_plan_hash(logical_plan),
            preview_hash=plan_preview_hash(logical_plan),
            payload=plan_snapshot_payload(
                logical_plan,
                recipe_snapshot=recipe_snapshot_payload(recipe_version),
            ),
        )
    )

    active_stage_id: uuid.UUID | None = None
    for step in logical_plan.steps:
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

    db.add(
        FermentationOgConsumption(
            fermentation_session_id=session.id,
            brew_measurement_id=og_leaf.id,
            consumed_value=og_leaf.value,
            consumed_unit=og_leaf.unit,
            consumed_at=now,
        )
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
            "og_measurement_id": str(og_leaf.id),
            "pitch_handoff_id": str(handoff.id),
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
