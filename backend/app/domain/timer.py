"""Brew timer projection and read-only past-due helpers (ADR-006)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.domain.enums import BrewTimerStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def derive_ends_at(started_at: datetime, target_duration_seconds: Optional[int]) -> Optional[datetime]:
    if target_duration_seconds is None:
        return None
    return started_at + timedelta(seconds=target_duration_seconds)


def project_status(
    *,
    elapsed_at: Optional[datetime],
    stopped_at: Optional[datetime],
    cancelled_at: Optional[datetime],
) -> str:
    """Deterministic status projection from authoritative timestamps.

    Precedence (terminal timestamps win; CANCELLED > STOPPED > ELAPSED > RUNNING):
    A STOPPED timer must not later become CANCELLED (cancel rejected if stopped).
    A CANCELLED timer must not later become ELAPSED (observe rejected if cancelled).
    An already ELAPSED timer must not create another elapsed event.
    """
    if cancelled_at is not None:
        return BrewTimerStatus.CANCELLED
    if stopped_at is not None:
        return BrewTimerStatus.STOPPED
    if elapsed_at is not None:
        return BrewTimerStatus.ELAPSED
    return BrewTimerStatus.RUNNING


def computed_past_due(
    *,
    ends_at: Optional[datetime],
    elapsed_at: Optional[datetime],
    stopped_at: Optional[datetime],
    cancelled_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> bool:
    """Read-only past-due flag. Never persists elapsed state."""
    if ends_at is None:
        return False
    if elapsed_at is not None or stopped_at is not None or cancelled_at is not None:
        return False
    server_now = now or utc_now()
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    if server_now.tzinfo is None:
        server_now = server_now.replace(tzinfo=timezone.utc)
    return server_now >= ends_at


def validate_label(label: str) -> Optional[str]:
    if label is None or not str(label).strip():
        return "label must be a non-blank string"
    if len(label.strip()) > 200:
        return "label must be at most 200 characters"
    return None


def validate_duration(target_duration_seconds: Optional[int]) -> Optional[str]:
    if target_duration_seconds is None:
        return None
    if target_duration_seconds <= 0:
        return "target_duration_seconds must be a positive integer when provided"
    return None
