"""Durable brew-day timers (E2A-4 / ADR-006).

Timers inform the brewer. Timers never control BrewSession, BrewStageOccurrence,
measurement, inventory, or handoff state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import BrewSession, BrewStageOccurrence, BrewTimer
from app.domain import timer as timer_domain
from app.domain.enums import BrewEventType, BrewSessionStatus, BrewTimerStatus
from app.schemas.brew_day import (
    TimerCancelRequest,
    TimerObserveElapsedRequest,
    TimerStartRequest,
    TimerStopRequest,
)
from app.services import brew_events as brew_events_service
from app.services import brew_session as brew_session_service
from app.services import idempotency as idempotency_service

SCOPE_BREW_SESSION = "BREW_SESSION"

# Explicit legality: no timer mutations after session is terminal.
_TERMINAL_SESSION_STATUSES = frozenset(
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


def _validation(code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": code, "message": message, **extra},
    )


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def timer_to_dict(timer: BrewTimer, *, now: Optional[datetime] = None) -> dict:
    """Read representation distinguishing persisted status from computed_past_due."""
    return {
        "id": timer.id,
        "brewery_id": timer.brewery_id,
        "brew_session_id": timer.brew_session_id,
        "stage_occurrence_id": timer.stage_occurrence_id,
        "label": timer.label,
        "target_duration_seconds": timer.target_duration_seconds,
        "started_at": _iso(timer.started_at),
        "client_started_at": _iso(timer.client_started_at),
        "ends_at": _iso(timer.ends_at),
        "elapsed_at": _iso(timer.elapsed_at),
        "stopped_at": _iso(timer.stopped_at),
        "cancelled_at": _iso(timer.cancelled_at),
        "status": timer.status,
        "computed_past_due": timer_domain.computed_past_due(
            ends_at=timer.ends_at,
            elapsed_at=timer.elapsed_at,
            stopped_at=timer.stopped_at,
            cancelled_at=timer.cancelled_at,
            now=now,
        ),
        "start_client_submission_id": timer.start_client_submission_id,
        "created_by": timer.created_by,
        "created_at": _iso(timer.created_at),
    }


def rebuild_status(timer: BrewTimer) -> str:
    projected = timer_domain.project_status(
        elapsed_at=timer.elapsed_at,
        stopped_at=timer.stopped_at,
        cancelled_at=timer.cancelled_at,
    )
    timer.status = projected
    return projected


async def _load_session_for_mutation(
    db: AsyncSession, session_id: str, expected_version: int
) -> BrewSession:
    session = await brew_session_service.get_brew_session(db, session_id)
    if expected_version != session.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONCURRENCY_CONFLICT",
                "message": "expected_session_version does not match current BrewSession.version",
                "expected_session_version": expected_version,
                "current_session_version": session.version,
            },
        )
    if session.status in _TERMINAL_SESSION_STATUSES:
        raise _illegal(
            "TIMER_SESSION_TERMINAL",
            "Timer mutations are not legal after the BrewSession is CLOSED, ABORTED, or HANDED_OFF",
            session_status=session.status,
        )
    return session


async def _load_timer(db: AsyncSession, timer_id: str) -> BrewTimer:
    result = await db.execute(select(BrewTimer).where(BrewTimer.id == timer_id))
    timer = result.scalar_one_or_none()
    if timer is None:
        raise HTTPException(status_code=404, detail="BrewTimer not found")
    return timer


async def _validate_stage_for_session(
    db: AsyncSession, *, session: BrewSession, stage_occurrence_id: Optional[str]
) -> None:
    if stage_occurrence_id is None:
        return
    result = await db.execute(
        select(BrewStageOccurrence).where(BrewStageOccurrence.id == stage_occurrence_id)
    )
    stage = result.scalar_one_or_none()
    if stage is None:
        raise _validation(
            "TIMER_STAGE_NOT_FOUND",
            "stage_occurrence_id does not exist",
            stage_occurrence_id=stage_occurrence_id,
        )
    if stage.brew_session_id != session.id:
        raise _illegal(
            "TIMER_STAGE_SESSION_MISMATCH",
            "stage_occurrence_id does not belong to this BrewSession",
            stage_occurrence_id=stage_occurrence_id,
            brew_session_id=session.id,
        )


async def start_timer(
    db: AsyncSession, session_id: str, payload: TimerStartRequest
) -> dict:
    actor_id = settings.default_actor_id
    fp = idempotency_service.fingerprint_payload(payload.model_dump(mode="json"))
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing, operation_type="START_TIMER", request_fingerprint=fp
    )
    if replay is not None:
        return replay

    label_err = timer_domain.validate_label(payload.label)
    if label_err:
        raise _validation("TIMER_INVALID_LABEL", label_err)
    duration_err = timer_domain.validate_duration(payload.target_duration_seconds)
    if duration_err:
        raise _validation("TIMER_INVALID_DURATION", duration_err)

    session = await _load_session_for_mutation(
        db, session_id, payload.expected_session_version
    )
    await _validate_stage_for_session(
        db, session=session, stage_occurrence_id=payload.stage_occurrence_id
    )

    version_before = session.version
    started_at = timer_domain.utc_now()
    ends_at = timer_domain.derive_ends_at(started_at, payload.target_duration_seconds)
    timer = BrewTimer(
        brewery_id=session.brewery_id,
        brew_session_id=session.id,
        stage_occurrence_id=payload.stage_occurrence_id,
        label=payload.label.strip(),
        target_duration_seconds=payload.target_duration_seconds,
        started_at=started_at,
        client_started_at=payload.client_started_at,
        ends_at=ends_at,
        status=BrewTimerStatus.RUNNING,
        start_client_submission_id=payload.client_submission_id,
        created_by=actor_id,
        created_at=started_at,
    )
    db.add(timer)
    await db.flush()

    await brew_events_service.append_brew_event(
        db,
        brewery_id=session.brewery_id,
        brew_session_id=session.id,
        brew_plan_id=session.brew_plan_id,
        event_type=BrewEventType.TIMER_STARTED,
        actor_id=actor_id,
        client_submission_id=payload.client_submission_id,
        client_occurred_at=payload.client_started_at,
        payload={
            "timer_id": timer.id,
            "label": timer.label,
            "target_duration_seconds": timer.target_duration_seconds,
            "started_at": _iso(timer.started_at),
            "ends_at": _iso(timer.ends_at),
            "stage_occurrence_id": timer.stage_occurrence_id,
        },
    )

    session.version = version_before + 1
    response = {
        "timer": timer_to_dict(timer),
        "session_version": session.version,
    }
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
        operation_type="START_TIMER",
        request_fingerprint=fp,
        resource_type="BrewTimer",
        resource_id=timer.id,
        http_status=201,
        response_snapshot=response,
        actor_id=actor_id,
        session_version_before=version_before,
        session_version_after=session.version,
    )
    await db.commit()
    return {
        "timer": timer_to_dict(timer),
        "session_version": session.version,
    }


async def stop_timer(db: AsyncSession, timer_id: str, payload: TimerStopRequest) -> dict:
    actor_id = settings.default_actor_id
    timer = await _load_timer(db, timer_id)
    session_id = timer.brew_session_id

    fp = idempotency_service.fingerprint_payload(
        {**payload.model_dump(mode="json"), "timer_id": timer_id}
    )
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing, operation_type="STOP_TIMER", request_fingerprint=fp
    )
    if replay is not None:
        return replay

    session = await _load_session_for_mutation(
        db, session_id, payload.expected_session_version
    )

    # Stop legal from RUNNING or ELAPSED; not from STOPPED/CANCELLED.
    if timer.cancelled_at is not None:
        raise _illegal(
            "TIMER_ALREADY_CANCELLED",
            "A CANCELLED timer cannot be stopped",
            timer_id=timer.id,
            status=timer.status,
        )
    if timer.stopped_at is not None:
        raise _illegal(
            "TIMER_ALREADY_STOPPED",
            "stopped_at may be set at most once",
            timer_id=timer.id,
            status=timer.status,
        )
    if timer.status not in (BrewTimerStatus.RUNNING, BrewTimerStatus.ELAPSED):
        raise _illegal(
            "TIMER_STOP_ILLEGAL",
            "Stop is only legal from RUNNING or ELAPSED",
            timer_id=timer.id,
            status=timer.status,
        )

    version_before = session.version
    timer.stopped_at = timer_domain.utc_now()
    rebuild_status(timer)

    await brew_events_service.append_brew_event(
        db,
        brewery_id=session.brewery_id,
        brew_session_id=session.id,
        brew_plan_id=session.brew_plan_id,
        event_type=BrewEventType.TIMER_STOPPED,
        actor_id=actor_id,
        client_submission_id=payload.client_submission_id,
        payload={
            "timer_id": timer.id,
            "stopped_at": _iso(timer.stopped_at),
            "status": timer.status,
        },
    )

    session.version = version_before + 1
    response = {"timer": timer_to_dict(timer), "session_version": session.version}
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
        operation_type="STOP_TIMER",
        request_fingerprint=fp,
        resource_type="BrewTimer",
        resource_id=timer.id,
        http_status=200,
        response_snapshot=response,
        actor_id=actor_id,
        session_version_before=version_before,
        session_version_after=session.version,
    )
    await db.commit()
    return {"timer": timer_to_dict(timer), "session_version": session.version}


async def cancel_timer(
    db: AsyncSession, timer_id: str, payload: TimerCancelRequest
) -> dict:
    actor_id = settings.default_actor_id
    timer = await _load_timer(db, timer_id)
    session_id = timer.brew_session_id

    fp = idempotency_service.fingerprint_payload(
        {**payload.model_dump(mode="json"), "timer_id": timer_id}
    )
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing, operation_type="CANCEL_TIMER", request_fingerprint=fp
    )
    if replay is not None:
        return replay

    session = await _load_session_for_mutation(
        db, session_id, payload.expected_session_version
    )

    # Cancel legal only from RUNNING (ADR-006).
    if timer.stopped_at is not None:
        raise _illegal(
            "TIMER_ALREADY_STOPPED",
            "A STOPPED timer cannot become CANCELLED",
            timer_id=timer.id,
            status=timer.status,
        )
    if timer.cancelled_at is not None:
        raise _illegal(
            "TIMER_ALREADY_CANCELLED",
            "cancelled_at may be set at most once",
            timer_id=timer.id,
            status=timer.status,
        )
    if timer.elapsed_at is not None or timer.status == BrewTimerStatus.ELAPSED:
        raise _illegal(
            "TIMER_CANCEL_ILLEGAL",
            "Cancel is only legal from RUNNING (not ELAPSED)",
            timer_id=timer.id,
            status=timer.status,
        )
    if timer.status != BrewTimerStatus.RUNNING:
        raise _illegal(
            "TIMER_CANCEL_ILLEGAL",
            "Cancel is only legal from RUNNING",
            timer_id=timer.id,
            status=timer.status,
        )

    version_before = session.version
    timer.cancelled_at = timer_domain.utc_now()
    rebuild_status(timer)

    await brew_events_service.append_brew_event(
        db,
        brewery_id=session.brewery_id,
        brew_session_id=session.id,
        brew_plan_id=session.brew_plan_id,
        event_type=BrewEventType.TIMER_CANCELLED,
        actor_id=actor_id,
        client_submission_id=payload.client_submission_id,
        payload={
            "timer_id": timer.id,
            "cancelled_at": _iso(timer.cancelled_at),
            "status": timer.status,
        },
    )

    session.version = version_before + 1
    response = {"timer": timer_to_dict(timer), "session_version": session.version}
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
        operation_type="CANCEL_TIMER",
        request_fingerprint=fp,
        resource_type="BrewTimer",
        resource_id=timer.id,
        http_status=200,
        response_snapshot=response,
        actor_id=actor_id,
        session_version_before=version_before,
        session_version_after=session.version,
    )
    await db.commit()
    return {"timer": timer_to_dict(timer), "session_version": session.version}


async def observe_elapsed(
    db: AsyncSession, timer_id: str, payload: TimerObserveElapsedRequest
) -> dict:
    actor_id = settings.default_actor_id
    timer = await _load_timer(db, timer_id)
    session_id = timer.brew_session_id

    fp = idempotency_service.fingerprint_payload(
        {**payload.model_dump(mode="json"), "timer_id": timer_id}
    )
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing, operation_type="OBSERVE_TIMER_ELAPSED", request_fingerprint=fp
    )
    if replay is not None:
        return replay

    session = await _load_session_for_mutation(
        db, session_id, payload.expected_session_version
    )

    if timer.ends_at is None:
        raise _illegal(
            "TIMER_NO_TARGET_END",
            "observe-elapsed requires a target duration / ends_at",
            timer_id=timer.id,
        )
    if timer.stopped_at is not None:
        raise _illegal(
            "TIMER_ALREADY_STOPPED",
            "A STOPPED timer cannot become ELAPSED",
            timer_id=timer.id,
            status=timer.status,
        )
    if timer.cancelled_at is not None:
        raise _illegal(
            "TIMER_ALREADY_CANCELLED",
            "A CANCELLED timer cannot become ELAPSED",
            timer_id=timer.id,
            status=timer.status,
        )
    if timer.elapsed_at is not None:
        raise _illegal(
            "TIMER_ALREADY_ELAPSED",
            "elapsed_at may be set at most once",
            timer_id=timer.id,
            status=timer.status,
        )

    now = timer_domain.utc_now()
    ends_at = timer.ends_at
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    if now < ends_at:
        raise _illegal(
            "TIMER_NOT_PAST_DUE",
            "observe-elapsed is only legal when server time is at or past ends_at",
            timer_id=timer.id,
            ends_at=_iso(timer.ends_at),
            server_now=_iso(now),
        )

    version_before = session.version

    timer.elapsed_at = now
    rebuild_status(timer)

    await brew_events_service.append_brew_event(
        db,
        brewery_id=session.brewery_id,
        brew_session_id=session.id,
        brew_plan_id=session.brew_plan_id,
        event_type=BrewEventType.TIMER_ELAPSED,
        actor_id=actor_id,
        client_submission_id=payload.client_submission_id,
        payload={
            "timer_id": timer.id,
            "elapsed_at": _iso(timer.elapsed_at),
            "ends_at": _iso(timer.ends_at),
            "status": timer.status,
            "process_unchanged": True,
        },
    )

    session.version = version_before + 1
    response = {"timer": timer_to_dict(timer), "session_version": session.version}
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
        operation_type="OBSERVE_TIMER_ELAPSED",
        request_fingerprint=fp,
        resource_type="BrewTimer",
        resource_id=timer.id,
        http_status=200,
        response_snapshot=response,
        actor_id=actor_id,
        session_version_before=version_before,
        session_version_after=session.version,
    )
    await db.commit()
    return {"timer": timer_to_dict(timer), "session_version": session.version}


async def list_session_timers(db: AsyncSession, session_id: str) -> dict:
    """Strictly read-only timer listing. Zero persistence side effects."""
    await brew_session_service.get_brew_session(db, session_id)
    result = await db.execute(
        select(BrewTimer)
        .where(BrewTimer.brew_session_id == session_id)
        .order_by(BrewTimer.started_at.asc(), BrewTimer.id.asc())
    )
    timers = result.scalars().all()
    now = timer_domain.utc_now()
    return {
        "brew_session_id": session_id,
        "timers": [timer_to_dict(t, now=now) for t in timers],
    }
