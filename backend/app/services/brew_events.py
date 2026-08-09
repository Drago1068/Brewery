"""Append-only BrewEvent writers (E2A-2). No update/delete APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BrewEvent
from app.domain.brew_day import json_safe


async def append_brew_event(
    db: AsyncSession,
    *,
    brewery_id: str,
    event_type: str,
    actor_id: str,
    payload: dict[str, Any],
    brew_plan_id: Optional[str] = None,
    brew_session_id: Optional[str] = None,
    client_occurred_at: Optional[datetime] = None,
    client_submission_id: Optional[str] = None,
    correlation_key: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
) -> BrewEvent:
    if brew_plan_id is None and brew_session_id is None:
        raise ValueError("BrewEvent requires brew_plan_id or brew_session_id")
    event = BrewEvent(
        brewery_id=brewery_id,
        brew_plan_id=brew_plan_id,
        brew_session_id=brew_session_id,
        event_type=event_type,
        actor_id=actor_id,
        payload=json_safe(payload),
        client_occurred_at=client_occurred_at,
        client_submission_id=client_submission_id,
        correlation_key=correlation_key,
    )
    if occurred_at is not None:
        event.occurred_at = occurred_at
    db.add(event)
    await db.flush()
    return event
