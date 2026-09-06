"""Fermentation completion eligibility, confirmation, and invalidation (§14)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from calculations.fermentation import StableGravityStatus
from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError, ValidationConflictError
from brewing_api.application.events import audit
from brewing_api.application.phase4.child_effects import (
    complete_fermentation_primary_timers,
    invalidate_and_reactivate_children,
)
from brewing_api.application.phase4.derived_gravity import (
    effective_gravity_leaves,
    latest_derived_gravity,
    recompute_derived_gravity,
)
from brewing_api.application.phase4.lifecycle import assert_command_allowed
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.domain.fermentation.constants import FERMENTATION_ELIGIBILITY_SCHEMA_VERSION
from brewing_api.domain.fermentation.models import (
    FermentationCompletionAssessment,
    FermentationJournalEvent,
    FermentationPlanSnapshot,
    FermentationSession,
    FermentationStageInstance,
    PackagingReadinessHandoff,
)
from brewing_api.domain.identity.models import User
from brewing_api.platform.time import utc_now


@dataclass(frozen=True)
class CompleteFermentationCommand:
    operation_id: str
    expected_revision: int | None = None
    override: bool = False
    override_reason: str | None = None


@dataclass(frozen=True)
class EligibilityResult:
    passed: bool
    outcome: str
    predicate_results: dict[str, Any]
    evidence_summary: dict[str, Any]


RULE_VERSION = FERMENTATION_ELIGIBILITY_SCHEMA_VERSION


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


def _active_fermentation_stage(
    db: Session, session_id: uuid.UUID
) -> FermentationStageInstance | None:
    return db.scalar(
        select(FermentationStageInstance).where(
            FermentationStageInstance.fermentation_session_id == session_id,
            FermentationStageInstance.canonical_stage_type == "ACTIVE_FERMENTATION",
        )
    )


def _attenuation_target(snapshot: FermentationPlanSnapshot | None) -> Decimal | None:
    if snapshot is None:
        return None
    recipe = snapshot.payload.get("recipe_snapshot") or {}
    raw = recipe.get("apparent_attenuation")
    if raw is None:
        return None
    return Decimal(str(raw))


def evaluate_fermentation_confirmation_predicates(
    db: Session,
    session: FermentationSession,
    *,
    override: bool = False,
    override_reason: str | None = None,
) -> EligibilityResult:
    """Evaluate F1–F3 against current effective evidence (no F4 / session-state gate).

    Used by §14.6 CLOSED packaging requalification and shared with CompleteFermentation
    after the ACTIVE (F4) gate passes.
    """
    predicate_results: dict[str, Any] = {}
    evidence: dict[str, Any] = {}

    leaves = effective_gravity_leaves(db, session.id)
    derived = latest_derived_gravity(db, session.id)
    if derived is None and leaves:
        derived = recompute_derived_gravity(db, session.id)

    snapshot = db.scalar(
        select(FermentationPlanSnapshot).where(
            FermentationPlanSnapshot.fermentation_session_id == session.id
        )
    )
    evidence["gravity_leaf_ids"] = [str(leaf.measurement_id) for leaf in leaves]
    if derived is not None:
        evidence["derived_gravity_snapshot_id"] = str(derived.id)
        evidence["stable_gravity_status"] = derived.stable_gravity_status
        evidence["window_measurement_ids"] = derived.window_measurement_ids

    if override:
        if not override_reason or not (10 <= len(override_reason) <= 1000):
            raise DomainError("Override reason must be 10 to 1000 characters", 422)
        if not leaves:
            raise ConflictError(
                "Override requires at least one valid gravity leaf",
                code="OVERRIDE_PROHIBITED",
            )
        predicate_results["F1"] = {"passed": True, "overridden": True}
        predicate_results["F2"] = {"passed": True, "overridden": True}
        predicate_results["F3"] = {"passed": True, "overridden": True}
        return EligibilityResult(
            passed=True,
            outcome="COMPLETION_OVERRIDDEN",
            predicate_results=predicate_results,
            evidence_summary=evidence,
        )

    # F1 — stable gravity
    stable_status = (
        derived.stable_gravity_status if derived else StableGravityStatus.INSUFFICIENT_EVIDENCE.value
    )
    f1_pass = stable_status == StableGravityStatus.STABLE.value
    predicate_results["F1"] = {"passed": f1_pass, "stable_gravity_status": stable_status}

    # F2 — attenuation target when specified
    target = _attenuation_target(snapshot)
    if target is None:
        f2_pass = True
        predicate_results["F2"] = {"passed": True, "not_applicable": True}
    else:
        ratio = derived.apparent_attenuation_ratio if derived else None
        f2_pass = ratio is not None and ratio >= target
        predicate_results["F2"] = {
            "passed": f2_pass,
            "target_ratio": str(target),
            "actual_ratio": None if ratio is None else str(ratio),
        }
        evidence["apparent_attenuation_ratio"] = None if ratio is None else str(ratio)

    # F3 — required non-stability checkpoints (vacuous pass when none materialized)
    f3_pass = True
    predicate_results["F3"] = {"passed": True, "checkpoints_materialized": False}

    passed = f1_pass and f2_pass and f3_pass
    return EligibilityResult(
        passed=passed,
        outcome="COMPLETION_ELIGIBLE" if passed else "INSUFFICIENT_EVIDENCE",
        predicate_results=predicate_results,
        evidence_summary=evidence,
    )


def evaluate_fermentation_eligibility(
    db: Session,
    session: FermentationSession,
    *,
    override: bool = False,
    override_reason: str | None = None,
) -> EligibilityResult:
    predicate_results: dict[str, Any] = {}
    evidence: dict[str, Any] = {}

    # F4 — session must be ACTIVE for CompleteFermentation (cannot override)
    f4_pass = session.status == "ACTIVE"
    predicate_results["F4"] = {"passed": f4_pass, "session_status": session.status}
    if not f4_pass:
        return EligibilityResult(
            passed=False,
            outcome="INSUFFICIENT_EVIDENCE",
            predicate_results=predicate_results,
            evidence_summary=evidence,
        )

    result = evaluate_fermentation_confirmation_predicates(
        db,
        session,
        override=override,
        override_reason=override_reason,
    )
    merged_predicates = {**predicate_results, **result.predicate_results}
    return EligibilityResult(
        passed=result.passed,
        outcome=result.outcome,
        predicate_results=merged_predicates,
        evidence_summary=result.evidence_summary,
    )


def _invalidate_current_assessments(
    db: Session,
    session: FermentationSession,
    *,
    cause_id: uuid.UUID,
) -> None:
    now = utc_now()
    current = list(
        db.scalars(
            select(FermentationCompletionAssessment).where(
                FermentationCompletionAssessment.fermentation_session_id == session.id,
                FermentationCompletionAssessment.is_current.is_(True),
                FermentationCompletionAssessment.assessment_kind.in_(
                    ("FERMENTATION", "CONDITIONING")
                ),
            )
        ).all()
    )
    for row in current:
        row.is_current = False
        row.outcome = "COMPLETION_INVALIDATED"
        row.invalidated_at = now
        row.invalidation_cause_id = cause_id


def _invalidate_current_handoff(
    db: Session,
    session: FermentationSession,
    *,
    cause_id: uuid.UUID,
) -> None:
    handoff = db.scalar(
        select(PackagingReadinessHandoff).where(
            PackagingReadinessHandoff.fermentation_session_id == session.id,
            PackagingReadinessHandoff.is_current.is_(True),
        )
    )
    if handoff is None:
        return
    now = utc_now()
    handoff.is_current = False
    handoff.readiness_status = "INVALIDATED"
    handoff.invalidated_at = now
    handoff.invalidation_cause_id = cause_id
    _journal(
        db,
        session.id,
        "PACKAGING_READINESS_HANDOFF_INVALIDATED",
        "Packaging readiness handoff invalidated",
        actor_id=None,
        event_data={
            "handoff_id": str(handoff.id),
            "cause_id": str(cause_id),
            "session_status": session.status,
        },
    )


def _reactivate_active_fermentation(
    db: Session,
    session: FermentationSession,
    *,
    cause_id: uuid.UUID,
) -> FermentationStageInstance:
    stage = _active_fermentation_stage(db, session.id)
    if stage is None:
        raise DomainError("Active fermentation stage is missing", 409)
    now = utc_now()
    stage.activation_ordinal += 1
    stage.status = "ACTIVE"
    stage.current_activation_started_at = now
    stage.current_completed_at = None
    stage.paused_at = None
    _journal(
        db,
        session.id,
        "FERMENTATION_STAGE_REACTIVATED",
        "Active fermentation stage reactivated after completion invalidation",
        event_data={
            "stage_instance_id": str(stage.id),
            "activation_ordinal": stage.activation_ordinal,
            "invalidation_cause_id": str(cause_id),
        },
    )
    return stage


def invalidate_after_fermentation_affecting_evidence(
    db: Session,
    session: FermentationSession,
    *,
    cause_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> bool:
    """Apply §14.6 invalidation when gravity/OG evidence changes completion assumptions."""
    if session.status == "ABORTED":
        return False
    if session.status == "CLOSED":
        _invalidate_current_handoff(db, session, cause_id=cause_id)
        _invalidate_current_assessments(db, session, cause_id=cause_id)
        _journal(
            db,
            session.id,
            "FERMENTATION_COMPLETION_INVALIDATED",
            "Completion invalidated on CLOSED session; handoff superseded",
            actor_id=actor_id,
            event_data={"cause_id": str(cause_id), "session_status": "CLOSED"},
        )
        return True

    terminal_complete = session.status in {
        "FERMENTATION_COMPLETE",
        "CONDITIONING",
        "CONDITIONING_COMPLETE",
        "COMPLETION_ASSESSED",
        "HANDOFF_READY",
    }
    if not terminal_complete:
        return False

    _invalidate_current_assessments(db, session, cause_id=cause_id)
    _invalidate_current_handoff(db, session, cause_id=cause_id)

    conditioning_stage = db.scalar(
        select(FermentationStageInstance).where(
            FermentationStageInstance.fermentation_session_id == session.id,
            FermentationStageInstance.canonical_stage_type == "CONDITIONING",
        )
    )
    if conditioning_stage is not None and conditioning_stage.status not in {"ABORTED", "PENDING"}:
        conditioning_stage.status = "INVALIDATED"
        from brewing_api.application.phase4.child_effects import cancel_conditioning_stage_children

        cancel_conditioning_stage_children(
            db,
            session,
            cause="COMPLETION_INVALIDATED",
            actor_id=actor_id,
        )

    session.status = "ACTIVE"
    session.fermentation_current_completed_at = None
    session.fermentation_completed_at = None
    session.conditioning_started_at = None
    session.conditioning_current_activation_started_at = None
    session.conditioning_current_completed_at = None
    session.conditioning_completed_at = None
    stage = _reactivate_active_fermentation(db, session, cause_id=cause_id)
    invalidate_and_reactivate_children(
        db,
        session,
        stage,
        cause="COMPLETION_INVALIDATED",
        actor_id=actor_id,
    )
    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_COMPLETION_INVALIDATED",
        "Fermentation completion invalidated; session returned to ACTIVE",
        actor_id=actor_id,
        stage_id=stage.id,
        event_data={"cause_id": str(cause_id)},
    )
    return True


def gravity_change_affects_completion(
    db: Session,
    session: FermentationSession,
    *,
    prior_stable_status: str | None,
    prior_attenuation: Decimal | None,
) -> bool:
    if session.status in {"ACTIVE", "ABORTED", "PAUSED"}:
        return False
    if session.status not in {
        "FERMENTATION_COMPLETE",
        "CONDITIONING",
        "CONDITIONING_COMPLETE",
        "COMPLETION_ASSESSED",
        "HANDOFF_READY",
        "CLOSED",
    }:
        return False
    derived = latest_derived_gravity(db, session.id)
    if derived is None:
        return True
    if prior_stable_status is not None and derived.stable_gravity_status != prior_stable_status:
        return True
    snapshot = db.scalar(
        select(FermentationPlanSnapshot).where(
            FermentationPlanSnapshot.fermentation_session_id == session.id
        )
    )
    target = _attenuation_target(snapshot)
    if target is None:
        return False
    ratio = derived.apparent_attenuation_ratio
    if prior_attenuation != ratio:
        if ratio is None or prior_attenuation is None:
            return True
        if (prior_attenuation >= target) != (ratio >= target):
            return True
    return False


def _persist_assessment(
    db: Session,
    session: FermentationSession,
    user: User,
    *,
    operation_id: str,
    result: EligibilityResult,
    confirmed: bool,
) -> FermentationCompletionAssessment:
    for row in db.scalars(
        select(FermentationCompletionAssessment).where(
            FermentationCompletionAssessment.fermentation_session_id == session.id,
            FermentationCompletionAssessment.is_current.is_(True),
            FermentationCompletionAssessment.assessment_kind == "FERMENTATION",
        )
    ).all():
        row.is_current = False

    now = utc_now()
    outcome = result.outcome
    if confirmed and outcome == "COMPLETION_ELIGIBLE":
        outcome = "COMPLETION_CONFIRMED"
    assessment = FermentationCompletionAssessment(
        fermentation_session_id=session.id,
        assessment_kind="FERMENTATION",
        outcome=outcome,
        is_current=True,
        rule_version=RULE_VERSION,
        predicate_results=result.predicate_results,
        evidence_summary=result.evidence_summary,
        actor_user_id=user.id,
        assessed_at=now,
        operation_id=operation_id,
        override_reason=None,
    )
    db.add(assessment)
    db.flush()
    return assessment


def complete_fermentation(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: CompleteFermentationCommand,
) -> tuple[FermentationSession, FermentationCompletionAssessment]:
    get_fermentation_session(db, user, session_id)
    document = {
        "command_name": "CompleteFermentation",
        "expected_revision": command.expected_revision,
        "override": command.override,
        "override_reason": command.override_reason,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "CompleteFermentation",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        session = db.get(FermentationSession, session_id)
        assessment = db.get(FermentationCompletionAssessment, replay.result_resource_id)
        assert session is not None and assessment is not None
        if replay.http_status == 422:
            raise ValidationConflictError(
                "Fermentation completion requirements are not satisfied",
                code="COMPLETION_INELIGIBLE",
                extra={"assessment_id": str(assessment.id), "outcome": assessment.outcome},
            )
        return session, assessment

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    try:
        assert_command_allowed("CompleteFermentation", session.status)
    except ConflictError:
        raise

    eligibility = evaluate_fermentation_eligibility(
        db,
        session,
        override=command.override,
        override_reason=command.override_reason,
    )

    if not eligibility.passed:
        assessment = _persist_assessment(
            db,
            session,
            user,
            operation_id=command.operation_id,
            result=eligibility,
            confirmed=False,
        )
        session.revision += 1
        _journal(
            db,
            session.id,
            "FERMENTATION_COMPLETION_ASSESSED",
            "Fermentation completion ineligible",
            actor_id=user.id,
            operation_id=command.operation_id,
            event_data={
                "assessment_id": str(assessment.id),
                "outcome": assessment.outcome,
            },
        )
        audit(db, user.id, "FERMENTATION_COMPLETION_INELIGIBLE", "FermentationSession", session.id)
        store_success(
            db,
            user.id,
            "CompleteFermentation",
            "FermentationSession",
            session.id,
            command.operation_id,
            document,
            {
                "assessment_id": str(assessment.id),
                "outcome": assessment.outcome,
                "status": session.status,
            },
            "FermentationCompletionAssessment",
            assessment.id,
            http_status=422,
        )
        db.commit()
        raise ValidationConflictError(
            "Fermentation completion requirements are not satisfied",
            code="COMPLETION_INELIGIBLE",
            extra={"assessment_id": str(assessment.id), "outcome": assessment.outcome},
        )

    now = utc_now()
    assessment = _persist_assessment(
        db,
        session,
        user,
        operation_id=command.operation_id,
        result=eligibility,
        confirmed=True,
    )
    if command.override:
        assessment.override_reason = command.override_reason

    stage = _active_fermentation_stage(db, session.id)
    if stage is not None:
        stage.status = "COMPLETED"
        stage.completed_at = stage.completed_at or now
        stage.first_completed_at = stage.first_completed_at or now
        stage.current_completed_at = now

    session.status = "FERMENTATION_COMPLETE"
    if session.fermentation_first_completed_at is None:
        session.fermentation_first_completed_at = now
    session.fermentation_current_completed_at = now
    session.fermentation_completed_at = now
    complete_fermentation_primary_timers(
        db,
        session,
        actor_id=user.id,
        operation_id=command.operation_id,
    )
    session.revision += 1

    _journal(
        db,
        session.id,
        "FERMENTATION_COMPLETED",
        "Fermentation marked complete",
        actor_id=user.id,
        operation_id=command.operation_id,
        stage_id=stage.id if stage else None,
        event_data={
            "assessment_id": str(assessment.id),
            "outcome": assessment.outcome,
        },
    )
    audit(db, user.id, "FERMENTATION_COMPLETED", "FermentationSession", session.id)
    store_success(
        db,
        user.id,
        "CompleteFermentation",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        {
            "assessment_id": str(assessment.id),
            "outcome": assessment.outcome,
            "status": session.status,
        },
        "FermentationCompletionAssessment",
        assessment.id,
    )
    db.commit()
    db.refresh(session)
    db.refresh(assessment)
    return session, assessment


def current_fermentation_assessment(
    db: Session, session_id: uuid.UUID
) -> FermentationCompletionAssessment | None:
    return db.scalar(
        select(FermentationCompletionAssessment).where(
            FermentationCompletionAssessment.fermentation_session_id == session_id,
            FermentationCompletionAssessment.is_current.is_(True),
            FermentationCompletionAssessment.assessment_kind == "FERMENTATION",
        )
    )


def serialize_assessment(assessment: FermentationCompletionAssessment) -> dict:
    return {
        "id": str(assessment.id),
        "assessment_kind": assessment.assessment_kind,
        "outcome": assessment.outcome,
        "is_current": assessment.is_current,
        "rule_version": assessment.rule_version,
        "predicate_results": assessment.predicate_results,
        "evidence_summary": assessment.evidence_summary,
        "assessed_at": assessment.assessed_at,
        "operation_id": assessment.operation_id,
        "override_reason": assessment.override_reason,
        "invalidated_at": assessment.invalidated_at,
        "invalidation_cause_id": None
        if assessment.invalidation_cause_id is None
        else str(assessment.invalidation_cause_id),
    }
