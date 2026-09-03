"""Conditioning lifecycle: Start/Skip/CompleteConditioning (§9.4, §14.3, §17)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError, ValidationConflictError
from brewing_api.application.events import audit
from brewing_api.application.phase4.child_effects import (
    complete_conditioning_primary_timers,
    create_conditioning_activation_children,
)
from brewing_api.application.phase4.completion import current_fermentation_assessment
from brewing_api.application.phase4.derived_gravity import effective_measurement_leaf
from brewing_api.application.phase4.lifecycle import assert_command_allowed
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.plan import plan_conditioning_required
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.domain.fermentation.constants import CONDITIONING_ELIGIBILITY_SCHEMA_VERSION
from brewing_api.domain.fermentation.models import (
    FermentationCompletionAssessment,
    FermentationJournalEvent,
    FermentationMeasurement,
    FermentationPlanSnapshot,
    FermentationSession,
    FermentationStageInstance,
)
from brewing_api.domain.identity.models import User
from brewing_api.platform.time import utc_now

RULE_VERSION = CONDITIONING_ELIGIBILITY_SCHEMA_VERSION


@dataclass(frozen=True)
class ConditioningCommand:
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


def _plan_snapshot(db: Session, session_id: uuid.UUID) -> FermentationPlanSnapshot | None:
    return db.scalar(
        select(FermentationPlanSnapshot).where(
            FermentationPlanSnapshot.fermentation_session_id == session_id
        )
    )


def require_current_fermentation_completion(
    db: Session, session: FermentationSession
) -> FermentationCompletionAssessment:
    """Handoff precondition: current confirmed fermentation assessment must exist."""
    assessment = current_fermentation_assessment(db, session.id)
    if assessment is None or assessment.outcome not in {
        "COMPLETION_CONFIRMED",
        "COMPLETION_WAIVED",
        "COMPLETION_OVERRIDDEN",
    }:
        raise ConflictError(
            "Current fermentation completion is missing or invalidated",
            code="STALE_HANDOFF",
        )
    if session.fermentation_current_completed_at is None:
        raise ConflictError(
            "Fermentation current completion timestamp is missing",
            code="STALE_HANDOFF",
        )
    return assessment


def current_conditioning_assessment(
    db: Session, session_id: uuid.UUID
) -> FermentationCompletionAssessment | None:
    return db.scalar(
        select(FermentationCompletionAssessment).where(
            FermentationCompletionAssessment.fermentation_session_id == session_id,
            FermentationCompletionAssessment.is_current.is_(True),
            FermentationCompletionAssessment.assessment_kind == "CONDITIONING",
        )
    )


def _persist_conditioning_assessment(
    db: Session,
    session: FermentationSession,
    user: User,
    *,
    operation_id: str,
    result: EligibilityResult,
    confirmed: bool,
    override_reason: str | None = None,
) -> FermentationCompletionAssessment:
    for row in db.scalars(
        select(FermentationCompletionAssessment).where(
            FermentationCompletionAssessment.fermentation_session_id == session.id,
            FermentationCompletionAssessment.is_current.is_(True),
            FermentationCompletionAssessment.assessment_kind == "CONDITIONING",
        )
    ).all():
        row.is_current = False

    now = utc_now()
    outcome = result.outcome
    if confirmed and outcome == "COMPLETION_ELIGIBLE":
        outcome = "COMPLETION_CONFIRMED"
    assessment = FermentationCompletionAssessment(
        fermentation_session_id=session.id,
        assessment_kind="CONDITIONING",
        outcome=outcome,
        is_current=True,
        schema_version=CONDITIONING_ELIGIBILITY_SCHEMA_VERSION,
        rule_version=RULE_VERSION,
        predicate_results=result.predicate_results,
        evidence_summary=result.evidence_summary,
        actor_user_id=user.id,
        assessed_at=now,
        operation_id=operation_id,
        override_reason=override_reason,
    )
    db.add(assessment)
    db.flush()
    return assessment


def evaluate_conditioning_eligibility(
    db: Session,
    session: FermentationSession,
    snapshot: FermentationPlanSnapshot | None,
    *,
    override: bool = False,
    override_reason: str | None = None,
) -> EligibilityResult:
    predicate_results: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    payload = snapshot.payload if snapshot else {}

    c0 = session.status == "CONDITIONING"
    predicate_results["C0"] = {"passed": c0, "session_status": session.status}
    if not c0:
        return EligibilityResult(
            passed=False,
            outcome="INSUFFICIENT_EVIDENCE",
            predicate_results=predicate_results,
            evidence_summary=evidence,
        )

    if override:
        if not override_reason or not (10 <= len(override_reason) <= 1000):
            raise DomainError("Override reason must be 10 to 1000 characters", 422)
        predicate_results["C1"] = {"passed": True, "overridden": True}
        predicate_results["C2"] = {"passed": True, "overridden": True}
        predicate_results["C3"] = {"passed": True, "overridden": True}
        predicate_results["C4"] = {"passed": True, "overridden": True}
        return EligibilityResult(
            passed=True,
            outcome="COMPLETION_OVERRIDDEN",
            predicate_results=predicate_results,
            evidence_summary=evidence,
        )

    duration_minutes = payload.get("conditioning_duration_minutes")
    if duration_minutes is None:
        c1 = True
        predicate_results["C1"] = {"passed": True, "not_applicable": True}
    else:
        anchor = session.conditioning_first_started_at
        if anchor is None:
            c1 = False
            predicate_results["C1"] = {"passed": False, "reason": "missing_first_started_at"}
        else:
            from brewing_api.application.phase4.time_validation import _coerce_aware

            elapsed = _coerce_aware(utc_now()) - _coerce_aware(anchor)
            required = timedelta(minutes=int(duration_minutes))
            c1 = elapsed >= required
            predicate_results["C1"] = {
                "passed": c1,
                "required_minutes": int(duration_minutes),
                "elapsed_seconds": int(elapsed.total_seconds()),
            }

    target_temp = payload.get("conditioning_temperature_c")
    if target_temp is None:
        c2 = True
        predicate_results["C2"] = {"passed": True, "not_applicable": True}
    else:
        tolerance = Decimal(str(payload.get("temperature_tolerance_c") or "1.0"))
        target = Decimal(str(target_temp))
        measurements = list(
            db.scalars(
                select(FermentationMeasurement).where(
                    FermentationMeasurement.fermentation_session_id == session.id,
                    FermentationMeasurement.measurement_type == "CONDITIONING_TEMPERATURE",
                    FermentationMeasurement.validation_status == "ACCEPTED",
                )
            ).all()
        )
        matched = False
        for measurement in measurements:
            _, correction = effective_measurement_leaf(db, measurement)
            value = correction.canonical_value if correction else measurement.canonical_value
            if abs(value - target) <= tolerance:
                matched = True
                evidence["conditioning_temperature_measurement_id"] = str(measurement.id)
                break
        c2 = matched
        predicate_results["C2"] = {
            "passed": c2,
            "target": str(target),
            "tolerance": str(tolerance),
        }

    c3 = True
    predicate_results["C3"] = {"passed": True, "checkpoints_materialized": False}

    if duration_minutes is not None and target_temp is not None:
        c4 = c1 and c2
        predicate_results["C4"] = {"passed": c4}
    else:
        c4 = True
        predicate_results["C4"] = {"passed": True, "not_applicable": True}

    passed = c1 and c2 and c3 and c4
    return EligibilityResult(
        passed=passed,
        outcome="COMPLETION_ELIGIBLE" if passed else "INSUFFICIENT_EVIDENCE",
        predicate_results=predicate_results,
        evidence_summary=evidence,
    )


def start_conditioning(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: ConditioningCommand,
) -> FermentationSession:
    get_fermentation_session(db, user, session_id)
    document = {
        "command_name": "StartConditioning",
        "expected_revision": command.expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "StartConditioning",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationSession, replay.result_resource_id)
        assert found is not None
        return found

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    assert_command_allowed("StartConditioning", session.status)

    ferm_assessment = require_current_fermentation_completion(db, session)
    snapshot = _plan_snapshot(db, session.id)
    if not plan_conditioning_required(None if snapshot is None else snapshot.payload):
        raise ConflictError(
            "Plan does not require conditioning; use SkipConditioning",
            code="CONDITIONING_NOT_REQUIRED",
        )

    existing = db.scalar(
        select(FermentationStageInstance).where(
            FermentationStageInstance.fermentation_session_id == session.id,
            FermentationStageInstance.canonical_stage_type == "CONDITIONING",
        )
    )
    now = utc_now()
    if existing is None:
        stage = FermentationStageInstance(
            fermentation_session_id=session.id,
            canonical_stage_type="CONDITIONING",
            occurrence_number=1,
            activation_ordinal=1,
            status="ACTIVE",
            started_at=now,
            first_started_at=now,
            current_activation_started_at=now,
        )
        db.add(stage)
        db.flush()
    elif existing.status == "INVALIDATED":
        existing.activation_ordinal += 1
        existing.status = "ACTIVE"
        existing.current_activation_started_at = now
        existing.current_completed_at = None
        existing.paused_at = None
        stage = existing
    elif existing.status in {"ACTIVE", "PAUSED", "COMPLETED"}:
        raise ConflictError(
            "Conditioning stage already exists and is not invalidated",
            code="STAGE_REPEAT_PROHIBITED",
            extra={"stage_instance_id": str(existing.id)},
        )
    else:
        raise ConflictError("Conditioning stage cannot be started", code="INVALID_TRANSITION")

    if session.conditioning_first_started_at is None:
        session.conditioning_first_started_at = now
    session.conditioning_started_at = now
    session.conditioning_current_activation_started_at = now
    session.conditioning_skipped = False
    session.status = "CONDITIONING"
    if snapshot and snapshot.payload.get("conditioning_mode"):
        session.conditioning_mode = snapshot.payload["conditioning_mode"]
    session.revision += 1

    duration_minutes = None if snapshot is None else snapshot.payload.get("conditioning_duration_minutes")
    duration_seconds = (
        int(duration_minutes) * 60 if duration_minutes is not None else 7 * 24 * 60 * 60
    )
    create_conditioning_activation_children(
        db,
        session,
        stage,
        actor_id=user.id,
        operation_id=command.operation_id,
        duration_seconds=duration_seconds,
    )
    _journal(
        db,
        session.id,
        "FERMENTATION_STAGE_ENTERED",
        "Conditioning started",
        actor_id=user.id,
        operation_id=command.operation_id,
        stage_id=stage.id,
        event_data={
            "fermentation_assessment_id": str(ferm_assessment.id),
            "activation_ordinal": stage.activation_ordinal,
            "fermentation_current_completed_at": session.fermentation_current_completed_at.isoformat()
            if session.fermentation_current_completed_at
            else None,
        },
    )
    audit(db, user.id, "CONDITIONING_STARTED", "FermentationSession", session.id)
    store_success(
        db,
        user.id,
        "StartConditioning",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        {
            "id": str(session.id),
            "status": session.status,
            "stage_instance_id": str(stage.id),
            "fermentation_assessment_id": str(ferm_assessment.id),
        },
        "FermentationSession",
        session.id,
    )
    db.commit()
    db.refresh(session)
    return session


def skip_conditioning(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: ConditioningCommand,
) -> tuple[FermentationSession, FermentationCompletionAssessment]:
    get_fermentation_session(db, user, session_id)
    document = {
        "command_name": "SkipConditioning",
        "expected_revision": command.expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "SkipConditioning",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        session = db.get(FermentationSession, session_id)
        assessment = db.get(FermentationCompletionAssessment, replay.result_resource_id)
        assert session is not None and assessment is not None
        return session, assessment

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    assert_command_allowed("SkipConditioning", session.status)
    require_current_fermentation_completion(db, session)

    snapshot = _plan_snapshot(db, session.id)
    if plan_conditioning_required(None if snapshot is None else snapshot.payload):
        raise ConflictError(
            "Conditioning is required by the plan snapshot",
            code="CONDITIONING_REQUIRED",
        )

    existing = db.scalar(
        select(FermentationStageInstance).where(
            FermentationStageInstance.fermentation_session_id == session.id,
            FermentationStageInstance.canonical_stage_type == "CONDITIONING",
        )
    )
    if existing is not None:
        raise ConflictError(
            "Conditioning stage already exists; cannot skip",
            code="STAGE_REPEAT_PROHIBITED",
        )

    result = EligibilityResult(
        passed=True,
        outcome="CONDITIONING_NOT_REQUIRED",
        predicate_results={"skip": {"passed": True, "conditioning_required": False}},
        evidence_summary={"path": "SkipConditioning"},
    )
    assessment = _persist_conditioning_assessment(
        db,
        session,
        user,
        operation_id=command.operation_id,
        result=result,
        confirmed=False,
    )

    session.status = "CONDITIONING_COMPLETE"
    session.conditioning_skipped = True
    session.conditioning_started_at = None
    session.conditioning_current_activation_started_at = None
    session.conditioning_current_completed_at = None
    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_CONDITIONING_SKIPPED",
        "Conditioning skipped per plan",
        actor_id=user.id,
        operation_id=command.operation_id,
        event_data={"assessment_id": str(assessment.id)},
    )
    audit(db, user.id, "CONDITIONING_SKIPPED", "FermentationSession", session.id)
    store_success(
        db,
        user.id,
        "SkipConditioning",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        {
            "id": str(session.id),
            "status": session.status,
            "assessment_id": str(assessment.id),
            "outcome": assessment.outcome,
        },
        "FermentationCompletionAssessment",
        assessment.id,
    )
    db.commit()
    db.refresh(session)
    db.refresh(assessment)
    return session, assessment


def complete_conditioning(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: ConditioningCommand,
) -> tuple[FermentationSession, FermentationCompletionAssessment]:
    get_fermentation_session(db, user, session_id)
    document = {
        "command_name": "CompleteConditioning",
        "expected_revision": command.expected_revision,
        "override": command.override,
        "override_reason": command.override_reason,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "CompleteConditioning",
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
                "Conditioning completion requirements are not satisfied",
                code="COMPLETION_INELIGIBLE",
                extra={"assessment_id": str(assessment.id), "outcome": assessment.outcome},
            )
        return session, assessment

    session = _lock_session(db, user, session_id)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")
    assert_command_allowed("CompleteConditioning", session.status)

    if command.override and command.override_reason is None:
        raise DomainError("Override reason is required when override=true", 422)
    # Deny client mode selection at completion
    snapshot = _plan_snapshot(db, session.id)
    eligibility = evaluate_conditioning_eligibility(
        db,
        session,
        snapshot,
        override=command.override,
        override_reason=command.override_reason,
    )

    if not eligibility.passed:
        assessment = _persist_conditioning_assessment(
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
            "FERMENTATION_CONDITIONING_ASSESSED",
            "Conditioning completion ineligible",
            actor_id=user.id,
            operation_id=command.operation_id,
            event_data={"assessment_id": str(assessment.id), "outcome": assessment.outcome},
        )
        store_success(
            db,
            user.id,
            "CompleteConditioning",
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
            "Conditioning completion requirements are not satisfied",
            code="COMPLETION_INELIGIBLE",
            extra={"assessment_id": str(assessment.id), "outcome": assessment.outcome},
        )

    now = utc_now()
    assessment = _persist_conditioning_assessment(
        db,
        session,
        user,
        operation_id=command.operation_id,
        result=eligibility,
        confirmed=True,
        override_reason=command.override_reason if command.override else None,
    )
    stage = db.scalar(
        select(FermentationStageInstance).where(
            FermentationStageInstance.fermentation_session_id == session.id,
            FermentationStageInstance.canonical_stage_type == "CONDITIONING",
        )
    )
    if stage is not None:
        stage.status = "COMPLETED"
        stage.completed_at = stage.completed_at or now
        stage.first_completed_at = stage.first_completed_at or now
        stage.current_completed_at = now

    session.status = "CONDITIONING_COMPLETE"
    if session.conditioning_first_completed_at is None:
        session.conditioning_first_completed_at = now
    session.conditioning_current_completed_at = now
    session.conditioning_completed_at = now
    complete_conditioning_primary_timers(
        db, session, actor_id=user.id, operation_id=command.operation_id
    )
    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_CONDITIONING_COMPLETED",
        "Conditioning marked complete",
        actor_id=user.id,
        operation_id=command.operation_id,
        stage_id=stage.id if stage else None,
        event_data={"assessment_id": str(assessment.id), "outcome": assessment.outcome},
    )
    audit(db, user.id, "CONDITIONING_COMPLETED", "FermentationSession", session.id)
    store_success(
        db,
        user.id,
        "CompleteConditioning",
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


def invalidate_after_conditioning_affecting_evidence(
    db: Session,
    session: FermentationSession,
    *,
    cause_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> bool:
    """§14.6 conditioning-only path: return to CONDITIONING and reactivate same stage."""
    if session.status in {"ABORTED", "CLOSED", "ACTIVE", "PAUSED", "FERMENTATION_COMPLETE"}:
        return False
    if session.status not in {
        "CONDITIONING",
        "CONDITIONING_COMPLETE",
        "COMPLETION_ASSESSED",
        "HANDOFF_READY",
    }:
        return False

    now = utc_now()
    for row in db.scalars(
        select(FermentationCompletionAssessment).where(
            FermentationCompletionAssessment.fermentation_session_id == session.id,
            FermentationCompletionAssessment.is_current.is_(True),
            FermentationCompletionAssessment.assessment_kind == "CONDITIONING",
        )
    ).all():
        row.is_current = False
        row.outcome = "COMPLETION_INVALIDATED"
        row.invalidated_at = now
        row.invalidation_cause_id = cause_id

    from brewing_api.application.phase4.completion import _invalidate_current_handoff

    _invalidate_current_handoff(db, session, cause_id=cause_id)

    stage = db.scalar(
        select(FermentationStageInstance).where(
            FermentationStageInstance.fermentation_session_id == session.id,
            FermentationStageInstance.canonical_stage_type == "CONDITIONING",
        )
    )
    if stage is None:
        return False

    from brewing_api.application.phase4.child_effects import cancel_conditioning_stage_children

    cancel_conditioning_stage_children(
        db, session, cause="COMPLETION_INVALIDATED", actor_id=actor_id
    )
    stage.activation_ordinal += 1
    stage.status = "ACTIVE"
    stage.current_activation_started_at = now
    stage.current_completed_at = None
    stage.paused_at = None

    session.status = "CONDITIONING"
    session.conditioning_current_completed_at = None
    session.conditioning_completed_at = None
    session.conditioning_started_at = now
    session.conditioning_current_activation_started_at = now
    duration_minutes = None
    snapshot = _plan_snapshot(db, session.id)
    if snapshot is not None:
        duration_minutes = snapshot.payload.get("conditioning_duration_minutes")
    duration_seconds = (
        int(duration_minutes) * 60 if duration_minutes is not None else 7 * 24 * 60 * 60
    )
    create_conditioning_activation_children(
        db,
        session,
        stage,
        actor_id=actor_id,
        duration_seconds=duration_seconds,
    )
    session.revision += 1
    _journal(
        db,
        session.id,
        "FERMENTATION_CONDITIONING_INVALIDATED",
        "Conditioning completion invalidated; session returned to CONDITIONING",
        actor_id=actor_id,
        stage_id=stage.id,
        event_data={"cause_id": str(cause_id), "activation_ordinal": stage.activation_ordinal},
    )
    return True
