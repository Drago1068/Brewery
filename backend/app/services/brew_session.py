"""BrewSession creation and read (E2A-1). Stage transitions are out of scope."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import BrewSession, BrewStageOccurrence
from app.domain.enums import (
    AuditAction,
    BREW_DAY_STAGE_SEQUENCE,
    BrewSessionStatus,
    BrewStageStatus,
)
from app.schemas.brew_day import (
    BrewSessionCreate,
    BrewSessionRead,
    StageOccurrenceSummary,
)
from app.services import audit
from app.services import brew_plan as brew_plan_service
from app.services import idempotency as idempotency_service

OPERATION_CREATE_BREW_SESSION = "CREATE_BREW_SESSION"
SCOPE_BREW_PLAN = "BREW_PLAN"


def _session_to_read(session: BrewSession) -> BrewSessionRead:
    stages = [
        StageOccurrenceSummary(
            id=s.id,
            stage_code=s.stage_code,
            sequence_no=s.sequence_no,
            status=s.status,
            entered_at=s.entered_at,
            exited_at=s.exited_at,
            skip_reason=s.skip_reason,
        )
        for s in sorted(session.stage_occurrences, key=lambda x: x.sequence_no)
    ]
    return BrewSessionRead(
        id=session.id,
        brew_plan_id=session.brew_plan_id,
        brewery_id=session.brewery_id,
        status=session.status,
        current_stage_code=session.current_stage_code,
        version=session.version,
        started_at=session.started_at,
        closed_at=session.closed_at,
        abort_reason=session.abort_reason,
        created_by=session.created_by,
        created_at=session.created_at,
        stage_occurrences=stages,
    )


async def create_brew_session(
    db: AsyncSession,
    brew_plan_id: str,
    payload: BrewSessionCreate,
) -> dict:
    fp = idempotency_service.fingerprint_payload(
        {"client_context": payload.client_context}
    )
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_PLAN,
        scope_id=brew_plan_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing,
        operation_type=OPERATION_CREATE_BREW_SESSION,
        request_fingerprint=fp,
    )
    if replay is not None:
        return replay

    plan = await brew_plan_service.get_brew_plan(db, brew_plan_id)

    # One session per plan (unique constraint); check early for clearer error.
    prior = await db.execute(
        select(BrewSession).where(BrewSession.brew_plan_id == brew_plan_id)
    )
    if prior.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "BREW_SESSION_EXISTS",
                "message": "Epic 2A allows only one BrewSession per BrewPlan",
                "brew_plan_id": brew_plan_id,
            },
        )

    actor = settings.default_actor_id
    session = BrewSession(
        brew_plan_id=plan.id,
        brewery_id=plan.brewery_id,
        status=BrewSessionStatus.PLANNED,
        current_stage_code=None,
        version=1,
        created_by=actor,
    )
    db.add(session)
    await db.flush()

    for index, stage_code in enumerate(BREW_DAY_STAGE_SEQUENCE, start=1):
        db.add(
            BrewStageOccurrence(
                brew_session_id=session.id,
                stage_code=stage_code.value,
                sequence_no=index,
                status=BrewStageStatus.PENDING,
            )
        )

    await db.flush()

    # Ensure stage rows are queryable and server defaults are loaded.
    loaded = await get_brew_session(db, session.id)

    await audit.record_audit(
        db,
        action=AuditAction.SESSION_CREATED,
        entity_type="BrewSession",
        entity_id=session.id,
        actor_id=actor,
        brewery_id=session.brewery_id,
        summary=f"BrewSession created for BrewPlan {plan.id}",
        details={
            "brew_session_id": session.id,
            "brew_plan_id": plan.id,
            "status": BrewSessionStatus.PLANNED,
            "stage_count": len(BREW_DAY_STAGE_SEQUENCE),
        },
    )

    response = _session_to_read(loaded).model_dump(mode="json")
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_PLAN,
        scope_id=brew_plan_id,
        client_submission_id=payload.client_submission_id,
        operation_type=OPERATION_CREATE_BREW_SESSION,
        request_fingerprint=fp,
        resource_type="BrewSession",
        resource_id=session.id,
        http_status=201,
        response_snapshot=response,
        actor_id=actor,
        session_version_before=None,
        session_version_after=session.version,
    )
    await db.commit()
    loaded = await get_brew_session(db, session.id)
    return _session_to_read(loaded).model_dump(mode="json")


async def get_brew_session(db: AsyncSession, session_id: str) -> BrewSession:
    result = await db.execute(
        select(BrewSession)
        .where(BrewSession.id == session_id)
        .options(selectinload(BrewSession.stage_occurrences))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BrewSession not found")
    return session


async def get_brew_session_read(db: AsyncSession, session_id: str) -> dict:
    """Side-effect free session read."""
    session = await get_brew_session(db, session_id)
    return _session_to_read(session).model_dump(mode="json")
