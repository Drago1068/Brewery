"""Phase 4 packaging readiness eligibility, assessment, and handoff (§14.4–14.5).

Slice 11 implements the waiver↔readiness interaction required by P4-FR-059/060
and AC-059/ADV-035. CloseFermentationSession remains outside this slice.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.application.events import audit
from brewing_api.application.phase4.completion import (
    current_fermentation_assessment,
    serialize_assessment,
)
from brewing_api.application.phase4.conditioning import current_conditioning_assessment
from brewing_api.application.phase4.lifecycle import assert_command_allowed
from brewing_api.application.phase4.og_consumption import current_og_consumption
from brewing_api.application.phase4.operations import replay_or_conflict, store_success
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.application.phase4.waivers import active_waiver_for_class
from brewing_api.domain.fermentation.constants import (
    ORIGINAL_GRAVITY_KNOWN,
    PACKAGING_READINESS_SCHEMA_VERSION,
    READINESS_ELIGIBILITY_SCHEMA_VERSION,
)
from brewing_api.domain.fermentation.models import (
    FermentationCompletionAssessment,
    FermentationJournalEvent,
    FermentationSession,
    PackagingReadinessHandoff,
)
from brewing_api.domain.identity.models import User
from brewing_api.platform.time import utc_now

RULE_VERSION = READINESS_ELIGIBILITY_SCHEMA_VERSION

_CONFIRMED_OUTCOMES = frozenset(
    {"COMPLETION_CONFIRMED", "COMPLETION_WAIVED", "COMPLETION_OVERRIDDEN"}
)
_CONDITIONING_OK_OUTCOMES = frozenset(
    {
        "COMPLETION_CONFIRMED",
        "COMPLETION_WAIVED",
        "COMPLETION_OVERRIDDEN",
        "CONDITIONING_NOT_REQUIRED",
    }
)


@dataclass(frozen=True)
class AssessReadinessCommand:
    operation_id: str
    expected_revision: int | None = None
    override: bool = False
    override_reason: str | None = None


@dataclass(frozen=True)
class RecordHandoffCommand:
    operation_id: str
    assessment_id: uuid.UUID
    expected_revision: int | None = None


@dataclass(frozen=True)
class ReadinessResult:
    r1: bool
    r2: bool
    r3: bool
    og_known: bool
    readiness_waiver_active: bool
    readiness_status: str
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


def current_packaging_assessment(
    db: Session, session_id: uuid.UUID
) -> FermentationCompletionAssessment | None:
    return db.scalar(
        select(FermentationCompletionAssessment).where(
            FermentationCompletionAssessment.fermentation_session_id == session_id,
            FermentationCompletionAssessment.assessment_kind == "PACKAGING",
            FermentationCompletionAssessment.is_current.is_(True),
        )
    )


def current_handoff(db: Session, session_id: uuid.UUID) -> PackagingReadinessHandoff | None:
    return db.scalar(
        select(PackagingReadinessHandoff).where(
            PackagingReadinessHandoff.fermentation_session_id == session_id,
            PackagingReadinessHandoff.is_current.is_(True),
        )
    )


def serialize_handoff(row: PackagingReadinessHandoff | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "handoff_version": row.handoff_version,
        "is_current": row.is_current,
        "readiness_status": row.readiness_status,
        "assessed_at": None if row.assessed_at is None else row.assessed_at.isoformat(),
        "assessment_id": None if row.assessment_id is None else str(row.assessment_id),
        "invalidated_at": None if row.invalidated_at is None else row.invalidated_at.isoformat(),
        "payload": row.payload or {},
        "schema_version": row.schema_version,
    }


def evaluate_packaging_readiness(
    db: Session,
    session: FermentationSession,
    *,
    override: bool = False,
    override_reason: str | None = None,
) -> ReadinessResult:
    fermentation = current_fermentation_assessment(db, session.id)
    conditioning = current_conditioning_assessment(db, session.id)
    og = current_og_consumption(db, session.id)
    og_waiver = active_waiver_for_class(db, session.id, ORIGINAL_GRAVITY_KNOWN)

    r1 = (
        fermentation is not None
        and fermentation.invalidated_at is None
        and fermentation.outcome in _CONFIRMED_OUTCOMES
    )
    r2 = bool(session.conditioning_skipped) or (
        conditioning is not None
        and conditioning.invalidated_at is None
        and conditioning.outcome in _CONDITIONING_OK_OUTCOMES
    )
    og_known = og is not None and og.og_availability == "KNOWN"
    readiness_waiver_active = og_waiver is not None

    predicate_results: dict[str, Any] = {
        "R1": {
            "passed": r1,
            "fermentation_assessment_id": None if fermentation is None else str(fermentation.id),
            "fermentation_outcome": None if fermentation is None else fermentation.outcome,
        },
        "R2": {
            "passed": r2,
            "conditioning_skipped": bool(session.conditioning_skipped),
            "conditioning_assessment_id": None if conditioning is None else str(conditioning.id),
            "conditioning_outcome": None if conditioning is None else conditioning.outcome,
        },
        "R3": {
            "og_known": og_known,
            "readiness_waiver_active": readiness_waiver_active,
            "overridden": False,
        },
    }
    evidence = {
        "og_consumption_id": None if og is None else str(og.id),
        "og_availability": None if og is None else og.og_availability,
        "original_gravity_known_waiver_id": None if og_waiver is None else str(og_waiver.id),
    }

    if override:
        if not override_reason or not (10 <= len(override_reason) <= 1000):
            raise DomainError("Override reason must be 10 to 1000 characters", 422)
        if not r1 or not r2:
            predicate_results["R3"]["override_attempted"] = True
            raise ConflictError(
                "Readiness override cannot bypass R1 or R2",
                code="OVERRIDE_PROHIBITED",
            )
        # R3-only bypass.
        r3 = True
        predicate_results["R3"] = {
            "passed": True,
            "og_known": og_known,
            "readiness_waiver_active": readiness_waiver_active,
            "overridden": True,
        }
        return ReadinessResult(
            r1=r1,
            r2=r2,
            r3=r3,
            og_known=og_known,
            readiness_waiver_active=readiness_waiver_active,
            readiness_status="READY_WITH_WAIVERS",
            outcome="COMPLETION_OVERRIDDEN",
            predicate_results=predicate_results,
            evidence_summary=evidence,
        )

    r3 = og_known or readiness_waiver_active
    predicate_results["R3"]["passed"] = r3

    if not r1 or not r2 or not r3:
        return ReadinessResult(
            r1=r1,
            r2=r2,
            r3=r3,
            og_known=og_known,
            readiness_waiver_active=readiness_waiver_active,
            readiness_status="NOT_READY",
            outcome="INSUFFICIENT_EVIDENCE",
            predicate_results=predicate_results,
            evidence_summary=evidence,
        )

    if readiness_waiver_active:
        status = "READY_WITH_WAIVERS"
        outcome = "COMPLETION_WAIVED"
    else:
        status = "READY"
        outcome = "COMPLETION_CONFIRMED"

    return ReadinessResult(
        r1=r1,
        r2=r2,
        r3=r3,
        og_known=og_known,
        readiness_waiver_active=readiness_waiver_active,
        readiness_status=status,
        outcome=outcome,
        predicate_results=predicate_results,
        evidence_summary=evidence,
    )


def _clear_current_packaging(db: Session, session_id: uuid.UUID) -> None:
    for row in db.scalars(
        select(FermentationCompletionAssessment).where(
            FermentationCompletionAssessment.fermentation_session_id == session_id,
            FermentationCompletionAssessment.assessment_kind == "PACKAGING",
            FermentationCompletionAssessment.is_current.is_(True),
        )
    ).all():
        row.is_current = False


def assess_packaging_readiness(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: AssessReadinessCommand,
) -> tuple[FermentationSession, FermentationCompletionAssessment]:
    get_fermentation_session(db, user, session_id)
    document = {
        "override": command.override,
        "override_reason": command.override_reason,
        "expected_revision": command.expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "AssessPackagingReadiness",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(FermentationCompletionAssessment, replay.result_resource_id)
        session = get_fermentation_session(db, user, session_id)
        if found:
            return session, found

    session = _lock_session(db, user, session_id)
    assert_command_allowed("AssessPackagingReadiness", session.status)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")

    try:
        result = evaluate_packaging_readiness(
            db,
            session,
            override=command.override,
            override_reason=command.override_reason,
        )
    except ConflictError as exc:
        if getattr(exc, "code", None) == "OVERRIDE_PROHIBITED":
            # Persist insufficient assessment; no READY handoff.
            _clear_current_packaging(db, session.id)
            now = utc_now()
            assessment = FermentationCompletionAssessment(
                fermentation_session_id=session.id,
                assessment_kind="PACKAGING",
                outcome="INSUFFICIENT_EVIDENCE",
                is_current=True,
                schema_version=READINESS_ELIGIBILITY_SCHEMA_VERSION,
                rule_version=RULE_VERSION,
                predicate_results={"override_prohibited": True, "R1_or_R2_false": True},
                evidence_summary={},
                actor_user_id=user.id,
                assessed_at=now,
                operation_id=command.operation_id,
                override_reason=command.override_reason,
            )
            db.add(assessment)
            session.revision += 1
            _journal(
                db,
                session.id,
                "PACKAGING_READINESS_ASSESSED",
                "Packaging readiness override prohibited",
                actor_id=user.id,
                operation_id=command.operation_id,
                event_data={"outcome": "INSUFFICIENT_EVIDENCE", "code": "OVERRIDE_PROHIBITED"},
            )
            db.commit()
            raise
        raise

    _clear_current_packaging(db, session.id)
    now = utc_now()
    assessment = FermentationCompletionAssessment(
        fermentation_session_id=session.id,
        assessment_kind="PACKAGING",
        outcome=result.outcome,
        is_current=True,
        schema_version=READINESS_ELIGIBILITY_SCHEMA_VERSION,
        rule_version=RULE_VERSION,
        predicate_results={
            **result.predicate_results,
            "readiness_status": result.readiness_status,
        },
        evidence_summary=result.evidence_summary,
        actor_user_id=user.id,
        assessed_at=now,
        operation_id=command.operation_id,
        override_reason=command.override_reason if command.override else None,
    )
    db.add(assessment)
    db.flush()

    if result.readiness_status in {"READY", "READY_WITH_WAIVERS"}:
        if session.status == "CONDITIONING_COMPLETE":
            session.status = "COMPLETION_ASSESSED"
            session.completion_assessed_at = now
            session.assessed_at = now
    # unsuccessful → remain CONDITIONING_COMPLETE (or existing status)

    # On R1/R2 failure from HANDOFF_READY path, invalidate current handoff.
    if (
        session.status == "HANDOFF_READY"
        and result.readiness_status == "NOT_READY"
    ):
        handoff = current_handoff(db, session.id)
        if handoff is not None and handoff.invalidated_at is None:
            handoff.readiness_status = "INVALIDATED"
            handoff.invalidated_at = now
            handoff.invalidation_cause_id = assessment.id
        session.status = "COMPLETION_ASSESSED"

    session.revision += 1
    _journal(
        db,
        session.id,
        "PACKAGING_READINESS_ASSESSED",
        f"Packaging readiness {result.readiness_status}",
        actor_id=user.id,
        operation_id=command.operation_id,
        event_data={
            "assessment_id": str(assessment.id),
            "readiness_status": result.readiness_status,
            "outcome": result.outcome,
        },
    )
    audit(db, user.id, "PACKAGING_READINESS_ASSESSED", "FermentationCompletionAssessment", assessment.id)
    store_success(
        db,
        user.id,
        "AssessPackagingReadiness",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        {
            "assessment_id": str(assessment.id),
            "readiness_status": result.readiness_status,
            "outcome": result.outcome,
            "status": session.status,
        },
        "FermentationCompletionAssessment",
        assessment.id,
    )
    db.commit()
    db.refresh(session)
    db.refresh(assessment)
    return session, assessment


def record_packaging_readiness_handoff(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    command: RecordHandoffCommand,
) -> tuple[FermentationSession, PackagingReadinessHandoff]:
    get_fermentation_session(db, user, session_id)
    document = {
        "assessment_id": str(command.assessment_id),
        "expected_revision": command.expected_revision,
    }
    replay = replay_or_conflict(
        db,
        user.id,
        "RecordPackagingReadinessHandoff",
        "FermentationSession",
        session_id,
        command.operation_id,
        document,
    )
    if replay and replay.result_resource_id:
        found = db.get(PackagingReadinessHandoff, replay.result_resource_id)
        session = get_fermentation_session(db, user, session_id)
        if found:
            return session, found

    session = _lock_session(db, user, session_id)
    assert_command_allowed("RecordPackagingReadinessHandoff", session.status)
    if command.expected_revision is not None and session.revision != command.expected_revision:
        raise ConflictError("Stale session revision", code="STALE_REVISION")

    assessment = db.get(FermentationCompletionAssessment, command.assessment_id)
    if (
        assessment is None
        or assessment.fermentation_session_id != session.id
        or assessment.assessment_kind != "PACKAGING"
    ):
        raise DomainError("Packaging readiness assessment not found", 422)

    current = current_handoff(db, session.id)
    if (
        current is not None
        and current.assessment_id == assessment.id
        and current.invalidated_at is None
    ):
        raise ConflictError(
            "Assessment already bound to current handoff",
            code="HANDOFF_ASSESSMENT_BOUND",
        )

    readiness_status = (assessment.predicate_results or {}).get("readiness_status")
    if readiness_status not in {"READY", "READY_WITH_WAIVERS", "NOT_READY"}:
        # Derive from outcome when older rows lack the field.
        if assessment.outcome == "COMPLETION_CONFIRMED":
            readiness_status = "READY"
        elif assessment.outcome in {"COMPLETION_WAIVED", "COMPLETION_OVERRIDDEN"}:
            readiness_status = "READY_WITH_WAIVERS"
        else:
            readiness_status = "NOT_READY"

    now = utc_now()
    version = 1 if current is None else current.handoff_version + 1
    if current is not None:
        current.is_current = False

    handoff = PackagingReadinessHandoff(
        fermentation_session_id=session.id,
        handoff_version=version,
        is_current=True,
        readiness_status=readiness_status,
        assessed_at=now,
        schema_version=PACKAGING_READINESS_SCHEMA_VERSION,
        payload={
            "assessment_outcome": assessment.outcome,
            "predicate_results": assessment.predicate_results,
            "evidence_summary": assessment.evidence_summary,
        },
        assessment_id=assessment.id,
    )
    db.add(handoff)
    db.flush()

    if readiness_status in {"READY", "READY_WITH_WAIVERS"}:
        session.status = "HANDOFF_READY"
        session.handoff_ready_at = now
        session.handoff_recorded_at = now
    else:
        # NOT_READY keeps COMPLETION_ASSESSED
        if session.status not in {"COMPLETION_ASSESSED", "CLOSED"}:
            session.status = "COMPLETION_ASSESSED"

    session.revision += 1
    _journal(
        db,
        session.id,
        "PACKAGING_READINESS_HANDOFF_RECORDED",
        f"Packaging readiness handoff {readiness_status}",
        actor_id=user.id,
        operation_id=command.operation_id,
        event_data={
            "handoff_id": str(handoff.id),
            "assessment_id": str(assessment.id),
            "readiness_status": readiness_status,
        },
    )
    audit(db, user.id, "PACKAGING_READINESS_HANDOFF_RECORDED", "PackagingReadinessHandoff", handoff.id)
    store_success(
        db,
        user.id,
        "RecordPackagingReadinessHandoff",
        "FermentationSession",
        session.id,
        command.operation_id,
        document,
        serialize_handoff(handoff),
        "PackagingReadinessHandoff",
        handoff.id,
    )
    db.commit()
    db.refresh(session)
    db.refresh(handoff)
    return session, handoff
