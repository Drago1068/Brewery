from __future__ import annotations

from datetime import UTC, datetime, timedelta

from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.domain.fermentation.models import (
    FermentationSession,
    FermentationStageInstance,
)
from brewing_api.platform.time import utc_now

FUTURE_SKEW = timedelta(minutes=5)
LATE_ENTRY_STAGE_HOURS = 24
LATE_ENTRY_CLOSED_HOURS = 24
CORRECTION_WINDOW_DAYS = 30


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise DomainError(
            "Timestamp must include an explicit UTC offset", 422, code="TIMESTAMP_NOT_UTC"
        )
    return value.astimezone(UTC)


def _coerce_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def validate_observed_at(
    observed_at: datetime,
    *,
    pitched_at: datetime,
    stage: FermentationStageInstance,
    server_now: datetime | None = None,
    require_explicit_offset: bool = True,
) -> datetime:
    if require_explicit_offset:
        observed = _aware(observed_at)
    else:
        observed = _coerce_aware(observed_at)
    pitch = _coerce_aware(pitched_at)
    now = server_now or utc_now()
    if observed > now + FUTURE_SKEW:
        raise DomainError(
            "observed_at cannot be more than five minutes in the future",
            422,
            code="TIMESTAMP_FUTURE",
        )
    if observed < pitch - FUTURE_SKEW:
        raise DomainError(
            "observed_at cannot precede pitch time", 422, code="TIMESTAMP_BEFORE_PITCH"
        )

    activation_started = (
        stage.current_activation_started_at or stage.first_started_at or stage.started_at
    )
    if stage.status in {"ACTIVE", "PAUSED"}:
        if activation_started is None:
            raise DomainError("Stage activation timestamp is missing", 409, code="STAGE_NOT_ACTIVE")
        lower = _coerce_aware(activation_started) - FUTURE_SKEW
        upper = now + FUTURE_SKEW
        if observed < lower or observed > upper:
            raise DomainError(
                "observed_at is outside the current activation window",
                422,
                code="TIMESTAMP_OUT_OF_WINDOW",
            )
        return observed

    if stage.status == "COMPLETED":
        first_started = stage.first_started_at or stage.started_at
        completed = stage.first_completed_at or stage.completed_at
        if first_started is None or completed is None:
            raise DomainError("Completed stage is missing activation timestamps", 409)
        lower = _coerce_aware(first_started) - FUTURE_SKEW
        upper = _coerce_aware(completed) + FUTURE_SKEW
        if observed < lower or observed > upper:
            raise DomainError(
                "observed_at is outside the completed stage window",
                422,
                code="TIMESTAMP_OUT_OF_WINDOW",
            )
        return observed

    if stage.status == "INVALIDATED":
        raise ConflictError("Stage is not active for new measurements", code="STAGE_NOT_ACTIVE")

    raise ConflictError("Stage is not active for new measurements", code="STAGE_NOT_ACTIVE")


def classify_late_entry(
    session: FermentationSession,
    stage: FermentationStageInstance,
    *,
    server_now: datetime | None = None,
    late_entry_reason: str | None = None,
) -> tuple[bool, bool | None]:
    now = server_now or utc_now()
    if session.status == "ABORTED":
        raise ConflictError(
            "New measurements are prohibited on an aborted session",
            code="TERMINAL_SESSION_EVIDENCE_PROHIBITED",
        )
    if stage.status in {"ACTIVE", "PAUSED"}:
        return False, None
    if session.status == "CLOSED":
        if session.closed_at is None:
            raise DomainError("Closed session is missing closed_at", 409)
        if now > session.closed_at + timedelta(hours=LATE_ENTRY_CLOSED_HOURS):
            raise ConflictError("Late entry window has closed", code="LATE_ENTRY_WINDOW_CLOSED")
        if not late_entry_reason or not (10 <= len(late_entry_reason) <= 1000):
            raise DomainError("Late entry reason must be 10 to 1000 characters", 422)
        return True, False
    if stage.status == "COMPLETED":
        completed = stage.first_completed_at or stage.completed_at
        if completed is None:
            raise DomainError("Completed stage is missing completion timestamp", 409)
        if now > completed + timedelta(hours=LATE_ENTRY_STAGE_HOURS):
            raise ConflictError("Late entry window has closed", code="LATE_ENTRY_WINDOW_CLOSED")
        if not late_entry_reason or not (10 <= len(late_entry_reason) <= 1000):
            raise DomainError("Late entry reason must be 10 to 1000 characters", 422)
        return True, True
    raise ConflictError("Stage is not eligible for measurement entry", code="STAGE_NOT_ACTIVE")


def assert_correction_window(
    session: FermentationSession, *, server_now: datetime | None = None
) -> None:
    now = server_now or utc_now()
    if session.status in {"CLOSED", "ABORTED"}:
        terminal = session.closed_at or session.aborted_at
        if terminal and now > _coerce_aware(terminal) + timedelta(days=CORRECTION_WINDOW_DAYS):
            raise ConflictError("Late entry window has closed", code="LATE_ENTRY_WINDOW_CLOSED")
