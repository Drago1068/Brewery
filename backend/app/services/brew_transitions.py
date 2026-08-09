"""BrewSession stage/session transition commands (E2A-2)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import BrewSession, BrewStageOccurrence
from app.domain.enums import (
    BrewEventType,
    BrewSessionStatus,
    BrewStageCode,
    BrewStageStatus,
    BrewTransitionCommand,
)
from app.schemas.brew_day import SessionTransitionRequest
from app.services import brew_events as brew_events_service
from app.services import brew_session as brew_session_service
from app.services import idempotency as idempotency_service

SCOPE_BREW_SESSION = "BREW_SESSION"

TERMINAL_SESSION_STATUSES = frozenset(
    {
        BrewSessionStatus.CLOSED,
        BrewSessionStatus.ABORTED,
        BrewSessionStatus.HANDED_OFF,
    }
)


def _illegal(code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": code, "message": message, **extra},
    )


def _stages_by_code(session: BrewSession) -> dict[str, BrewStageOccurrence]:
    return {s.stage_code: s for s in session.stage_occurrences}


def _active_stages(session: BrewSession) -> list[BrewStageOccurrence]:
    return [s for s in session.stage_occurrences if s.status == BrewStageStatus.ACTIVE]


def _next_stage_after(
    session: BrewSession, current: BrewStageOccurrence
) -> Optional[BrewStageOccurrence]:
    ordered = sorted(session.stage_occurrences, key=lambda s: s.sequence_no)
    for stage in ordered:
        if stage.sequence_no > current.sequence_no:
            return stage
    return None


async def apply_skip_measurement_side_effects(
    db: AsyncSession,
    *,
    session: BrewSession,
    stage: BrewStageOccurrence,
) -> None:
    """E2A-3 hook: auto-MISS remaining REQUIRED measurements on skip (same txn).

    Measurement tables do not exist in E2A-2. This no-op preserves the ADR-004
    contract so E2A-3 can extend without redesigning the state machine.
    """
    return None


def _fingerprint(payload: SessionTransitionRequest) -> str:
    body: dict[str, Any] = {
        "command": payload.command,
        "skip_reason": payload.skip_reason,
        "abort_reason": payload.abort_reason,
        "client_occurred_at": (
            payload.client_occurred_at.isoformat() if payload.client_occurred_at else None
        ),
    }
    return idempotency_service.fingerprint_payload(body)


async def apply_transition(
    db: AsyncSession,
    session_id: str,
    payload: SessionTransitionRequest,
) -> dict:
    fp = _fingerprint(payload)
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing,
        operation_type=payload.command,
        request_fingerprint=fp,
    )
    if replay is not None:
        return replay

    session = await brew_session_service.get_brew_session(db, session_id)
    version_before = session.version

    if payload.expected_session_version != session.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONCURRENCY_CONFLICT",
                "message": "expected_session_version does not match current BrewSession.version",
                "expected_session_version": payload.expected_session_version,
                "current_session_version": session.version,
            },
        )

    if session.status in TERMINAL_SESSION_STATUSES:
        raise _illegal(
            "SESSION_TERMINAL",
            f"Cannot transition session in terminal status {session.status}",
            status=session.status,
        )

    actor = settings.default_actor_id
    now = datetime.now(timezone.utc)
    command = payload.command

    if command == BrewTransitionCommand.START_SESSION:
        await _start_session(db, session, actor, now, payload)
    elif command == BrewTransitionCommand.ADVANCE_STAGE:
        await _advance_stage(db, session, actor, now, payload)
    elif command == BrewTransitionCommand.SKIP_STAGE:
        await _skip_stage(db, session, actor, now, payload)
    elif command == BrewTransitionCommand.PAUSE_SESSION:
        await _pause_session(db, session, actor, now, payload)
    elif command == BrewTransitionCommand.RESUME_SESSION:
        await _resume_session(db, session, actor, now, payload)
    elif command == BrewTransitionCommand.ABORT_SESSION:
        await _abort_session(db, session, actor, now, payload)
    elif command == BrewTransitionCommand.CLOSE_SESSION:
        await _close_session(db, session, actor, now, payload)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "UNKNOWN_COMMAND", "message": f"Unsupported command {command}"},
        )

    session.version = version_before + 1
    await db.flush()

    response = await brew_session_service.get_brew_session_read(db, session.id)
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
        operation_type=command,
        request_fingerprint=fp,
        resource_type="BrewSession",
        resource_id=session.id,
        http_status=200,
        response_snapshot=response,
        actor_id=actor,
        session_version_before=version_before,
        session_version_after=session.version,
    )
    await db.commit()
    return await brew_session_service.get_brew_session_read(db, session.id)


async def _append(
    db: AsyncSession,
    session: BrewSession,
    *,
    event_type: str,
    actor_id: str,
    payload: dict[str, Any],
    client_occurred_at: Optional[datetime],
    client_submission_id: str,
) -> None:
    await brew_events_service.append_brew_event(
        db,
        brewery_id=session.brewery_id,
        brew_plan_id=session.brew_plan_id,
        brew_session_id=session.id,
        event_type=event_type,
        actor_id=actor_id,
        payload=payload,
        client_occurred_at=client_occurred_at,
        client_submission_id=client_submission_id,
    )


async def _start_session(
    db: AsyncSession,
    session: BrewSession,
    actor: str,
    now: datetime,
    payload: SessionTransitionRequest,
) -> None:
    if session.status != BrewSessionStatus.PLANNED:
        raise _illegal(
            "ILLEGAL_TRANSITION",
            "START_SESSION requires session status PLANNED",
            status=session.status,
        )
    if _active_stages(session):
        raise _illegal("ACTIVE_STAGE_EXISTS", "Session already has an ACTIVE stage")

    stages = _stages_by_code(session)
    pre_brew = stages.get(BrewStageCode.PRE_BREW)
    if pre_brew is None:
        raise _illegal("STAGE_MISSING", "PRE_BREW stage occurrence is missing")
    if pre_brew.status != BrewStageStatus.PENDING:
        raise _illegal(
            "ILLEGAL_STAGE_STATE",
            "START_SESSION requires PRE_BREW PENDING",
            stage_status=pre_brew.status,
        )

    session.status = BrewSessionStatus.IN_PROGRESS
    session.started_at = now
    session.current_stage_code = BrewStageCode.PRE_BREW
    pre_brew.status = BrewStageStatus.ACTIVE
    pre_brew.entered_at = now

    await _append(
        db,
        session,
        event_type=BrewEventType.SESSION_STARTED,
        actor_id=actor,
        payload={"brew_session_id": session.id, "from_status": BrewSessionStatus.PLANNED},
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
    )
    await _append(
        db,
        session,
        event_type=BrewEventType.STAGE_ENTERED,
        actor_id=actor,
        payload={
            "stage_code": BrewStageCode.PRE_BREW,
            "stage_occurrence_id": pre_brew.id,
            "sequence_no": pre_brew.sequence_no,
        },
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
    )


async def _require_in_progress_not_paused(session: BrewSession, command: str) -> None:
    if session.status == BrewSessionStatus.PAUSED:
        raise _illegal(
            "SESSION_PAUSED",
            f"{command} is illegal while session is PAUSED",
        )
    if session.status != BrewSessionStatus.IN_PROGRESS:
        raise _illegal(
            "ILLEGAL_TRANSITION",
            f"{command} requires session status IN_PROGRESS",
            status=session.status,
        )


async def _advance_stage(
    db: AsyncSession,
    session: BrewSession,
    actor: str,
    now: datetime,
    payload: SessionTransitionRequest,
) -> None:
    await _require_in_progress_not_paused(session, BrewTransitionCommand.ADVANCE_STAGE)
    active = _active_stages(session)
    if len(active) != 1:
        raise _illegal(
            "ACTIVE_STAGE_INVARIANT",
            "ADVANCE_STAGE requires exactly one ACTIVE stage",
            active_count=len(active),
        )
    current = active[0]
    nxt = _next_stage_after(session, current)
    if nxt is not None and nxt.status != BrewStageStatus.PENDING:
        raise _illegal(
            "STAGE_ORDER_VIOLATION",
            "Next stage is not PENDING; backward reopen is forbidden",
            next_stage=nxt.stage_code,
            next_status=nxt.status,
        )

    current.status = BrewStageStatus.COMPLETED
    current.exited_at = now
    await _append(
        db,
        session,
        event_type=BrewEventType.STAGE_EXITED,
        actor_id=actor,
        payload={
            "stage_code": current.stage_code,
            "stage_occurrence_id": current.id,
            "exit_kind": "COMPLETED",
        },
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
    )

    if nxt is None:
        session.current_stage_code = None
        return

    nxt.status = BrewStageStatus.ACTIVE
    nxt.entered_at = now
    session.current_stage_code = nxt.stage_code
    await _append(
        db,
        session,
        event_type=BrewEventType.STAGE_ENTERED,
        actor_id=actor,
        payload={
            "stage_code": nxt.stage_code,
            "stage_occurrence_id": nxt.id,
            "sequence_no": nxt.sequence_no,
        },
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
    )


async def _skip_stage(
    db: AsyncSession,
    session: BrewSession,
    actor: str,
    now: datetime,
    payload: SessionTransitionRequest,
) -> None:
    await _require_in_progress_not_paused(session, BrewTransitionCommand.SKIP_STAGE)
    if not payload.skip_reason or not payload.skip_reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "SKIP_REASON_REQUIRED",
                "message": "SKIP_STAGE requires skip_reason",
            },
        )

    # Prefer ACTIVE stage; allow explicit skip of next PENDING only via ACTIVE path.
    active = _active_stages(session)
    if len(active) != 1:
        raise _illegal(
            "ACTIVE_STAGE_INVARIANT",
            "SKIP_STAGE requires exactly one ACTIVE stage",
            active_count=len(active),
        )
    current = active[0]
    nxt = _next_stage_after(session, current)

    current.status = BrewStageStatus.SKIPPED
    current.exited_at = now
    current.skip_reason = payload.skip_reason.strip()

    await apply_skip_measurement_side_effects(db, session=session, stage=current)

    await _append(
        db,
        session,
        event_type=BrewEventType.STAGE_SKIPPED,
        actor_id=actor,
        payload={
            "stage_code": current.stage_code,
            "stage_occurrence_id": current.id,
            "skip_reason": current.skip_reason,
        },
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
    )

    if nxt is None:
        session.current_stage_code = None
        return
    if nxt.status != BrewStageStatus.PENDING:
        raise _illegal(
            "STAGE_ORDER_VIOLATION",
            "Cannot activate non-PENDING next stage after skip",
            next_status=nxt.status,
        )

    nxt.status = BrewStageStatus.ACTIVE
    nxt.entered_at = now
    session.current_stage_code = nxt.stage_code
    await _append(
        db,
        session,
        event_type=BrewEventType.STAGE_ENTERED,
        actor_id=actor,
        payload={
            "stage_code": nxt.stage_code,
            "stage_occurrence_id": nxt.id,
            "sequence_no": nxt.sequence_no,
        },
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
    )


async def _pause_session(
    db: AsyncSession,
    session: BrewSession,
    actor: str,
    now: datetime,
    payload: SessionTransitionRequest,
) -> None:
    if session.status != BrewSessionStatus.IN_PROGRESS:
        raise _illegal(
            "ILLEGAL_TRANSITION",
            "PAUSE_SESSION requires session status IN_PROGRESS",
            status=session.status,
        )
    session.status = BrewSessionStatus.PAUSED
    await _append(
        db,
        session,
        event_type=BrewEventType.SESSION_PAUSED,
        actor_id=actor,
        payload={"brew_session_id": session.id, "at": now.isoformat()},
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
    )


async def _resume_session(
    db: AsyncSession,
    session: BrewSession,
    actor: str,
    now: datetime,
    payload: SessionTransitionRequest,
) -> None:
    if session.status != BrewSessionStatus.PAUSED:
        raise _illegal(
            "ILLEGAL_TRANSITION",
            "RESUME_SESSION requires session status PAUSED",
            status=session.status,
        )
    session.status = BrewSessionStatus.IN_PROGRESS
    await _append(
        db,
        session,
        event_type=BrewEventType.SESSION_RESUMED,
        actor_id=actor,
        payload={"brew_session_id": session.id, "at": now.isoformat()},
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
    )


async def _abort_session(
    db: AsyncSession,
    session: BrewSession,
    actor: str,
    now: datetime,
    payload: SessionTransitionRequest,
) -> None:
    if session.status in TERMINAL_SESSION_STATUSES:
        raise _illegal(
            "SESSION_TERMINAL",
            "ABORT_SESSION cannot run on a terminal session",
            status=session.status,
        )
    if session.status not in (
        BrewSessionStatus.PLANNED,
        BrewSessionStatus.IN_PROGRESS,
        BrewSessionStatus.PAUSED,
    ):
        raise _illegal(
            "ILLEGAL_TRANSITION",
            f"ABORT_SESSION not permitted from {session.status}",
            status=session.status,
        )
    if not payload.abort_reason or not payload.abort_reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "ABORT_REASON_REQUIRED",
                "message": "ABORT_SESSION requires abort_reason",
            },
        )

    prior = session.status
    session.status = BrewSessionStatus.ABORTED
    session.abort_reason = payload.abort_reason.strip()
    session.closed_at = now
    # Preserve stage historical facts; do not fabricate measurements or handoff.
    await _append(
        db,
        session,
        event_type=BrewEventType.SESSION_ABORTED,
        actor_id=actor,
        payload={
            "brew_session_id": session.id,
            "from_status": prior,
            "abort_reason": session.abort_reason,
        },
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
    )


async def _close_session(
    db: AsyncSession,
    session: BrewSession,
    actor: str,
    now: datetime,
    payload: SessionTransitionRequest,
) -> None:
    """E2A-2 close: IN_PROGRESS → CLOSED. Measurement REQUIRED gates arrive in E2A-3."""
    if session.status == BrewSessionStatus.PAUSED:
        raise _illegal(
            "SESSION_PAUSED",
            "CLOSE_SESSION is illegal while session is PAUSED",
        )
    if session.status != BrewSessionStatus.IN_PROGRESS:
        raise _illegal(
            "ILLEGAL_TRANSITION",
            "CLOSE_SESSION requires session status IN_PROGRESS",
            status=session.status,
        )
    # E2A-3 will reject close while REQUIRED measurements remain PENDING.
    session.status = BrewSessionStatus.CLOSED
    session.closed_at = now
    await _append(
        db,
        session,
        event_type=BrewEventType.SESSION_CLOSED,
        actor_id=actor,
        payload={"brew_session_id": session.id},
        client_occurred_at=payload.client_occurred_at,
        client_submission_id=payload.client_submission_id,
    )
