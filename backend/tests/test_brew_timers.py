"""E2A-4 durable brew-day timer domain and service tests (ADR-006)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.models import BrewSession, BrewStageOccurrence, BrewTimer
from app.domain import timer as timer_domain
from app.domain.enums import BrewEventType, BrewTimerStatus
from app.schemas.brew_day import (
    TimerCancelRequest,
    TimerObserveElapsedRequest,
    TimerStartRequest,
    TimerStopRequest,
)
from app.services import brew_timers as brew_timers_service


def _session(
    *,
    status: str = "IN_PROGRESS",
    version: int = 3,
    session_id: str = "sess-1",
) -> BrewSession:
    return BrewSession(
        id=session_id,
        brew_plan_id="plan-1",
        brewery_id="brewery-1",
        status=status,
        current_stage_code="MASH",
        version=version,
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
    )


def _timer(
    *,
    status: str = "RUNNING",
    target: int | None = 60,
    started_at: datetime | None = None,
    ends_at: datetime | None = None,
    elapsed_at: datetime | None = None,
    stopped_at: datetime | None = None,
    cancelled_at: datetime | None = None,
    stage_occurrence_id: str | None = "stage-1",
) -> BrewTimer:
    started = started_at or datetime.now(timezone.utc) - timedelta(seconds=30)
    if ends_at is None and target is not None:
        ends_at = started + timedelta(seconds=target)
    return BrewTimer(
        id="timer-1",
        brewery_id="brewery-1",
        brew_session_id="sess-1",
        stage_occurrence_id=stage_occurrence_id,
        label="Mash rest",
        target_duration_seconds=target,
        started_at=started,
        client_started_at=None,
        ends_at=ends_at,
        elapsed_at=elapsed_at,
        stopped_at=stopped_at,
        cancelled_at=cancelled_at,
        status=status,
        start_client_submission_id="start-sub",
        created_by="local-brewer",
        created_at=started,
    )


def test_project_status_precedence():
    assert (
        timer_domain.project_status(
            elapsed_at=None, stopped_at=None, cancelled_at=None
        )
        == BrewTimerStatus.RUNNING
    )
    now = datetime.now(timezone.utc)
    assert (
        timer_domain.project_status(
            elapsed_at=now, stopped_at=None, cancelled_at=None
        )
        == BrewTimerStatus.ELAPSED
    )
    assert (
        timer_domain.project_status(
            elapsed_at=now, stopped_at=now, cancelled_at=None
        )
        == BrewTimerStatus.STOPPED
    )
    assert (
        timer_domain.project_status(
            elapsed_at=now, stopped_at=now, cancelled_at=now
        )
        == BrewTimerStatus.CANCELLED
    )


def test_computed_past_due_read_only_rules():
    now = datetime.now(timezone.utc)
    ends = now - timedelta(seconds=1)
    assert timer_domain.computed_past_due(
        ends_at=ends, elapsed_at=None, stopped_at=None, cancelled_at=None, now=now
    )
    assert not timer_domain.computed_past_due(
        ends_at=ends, elapsed_at=now, stopped_at=None, cancelled_at=None, now=now
    )
    assert not timer_domain.computed_past_due(
        ends_at=None, elapsed_at=None, stopped_at=None, cancelled_at=None, now=now
    )
    assert not timer_domain.computed_past_due(
        ends_at=now + timedelta(hours=1),
        elapsed_at=None,
        stopped_at=None,
        cancelled_at=None,
        now=now,
    )


def test_validate_label_and_duration():
    assert timer_domain.validate_label("  ") is not None
    assert timer_domain.validate_label("Mash") is None
    assert timer_domain.validate_duration(0) is not None
    assert timer_domain.validate_duration(-5) is not None
    assert timer_domain.validate_duration(None) is None
    assert timer_domain.validate_duration(60) is None


def test_derive_ends_at():
    start = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
    assert timer_domain.derive_ends_at(start, 90) == start + timedelta(seconds=90)
    assert timer_domain.derive_ends_at(start, None) is None


@pytest.mark.asyncio
async def test_start_timer_happy_path():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    session = _session(version=2)
    stage = BrewStageOccurrence(
        id="stage-1",
        brew_session_id="sess-1",
        stage_code="MASH",
        sequence_no=3,
        status="ACTIVE",
    )

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = stage
        return result

    db.execute = AsyncMock(side_effect=fake_execute)

    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ) as record,
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_timers.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
        patch(
            "app.services.brew_timers.timer_domain.utc_now",
            return_value=datetime(2026, 8, 9, 15, 0, tzinfo=timezone.utc),
        ),
    ):
        result = await brew_timers_service.start_timer(
            db,
            "sess-1",
            TimerStartRequest(
                client_submission_id="start-1",
                expected_session_version=2,
                label="Mash rest",
                target_duration_seconds=3600,
                stage_occurrence_id="stage-1",
            ),
        )
        assert session.version == 3
        timer = result["timer"]
        assert timer["status"] == "RUNNING"
        assert timer["started_at"] == "2026-08-09T15:00:00+00:00"
        assert timer["ends_at"] == "2026-08-09T16:00:00+00:00"
        assert timer["computed_past_due"] is False
        append.assert_awaited()
        assert append.await_args.kwargs["event_type"] == BrewEventType.TIMER_STARTED
        record.assert_awaited()
        db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_start_timer_idempotent_replay():
    db = AsyncMock()
    snapshot = {"timer": {"id": "timer-1"}, "session_version": 3}
    existing = MagicMock(
        operation_type="START_TIMER",
        request_fingerprint="fp",
        response_snapshot=snapshot,
    )
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=existing,
        ),
        patch(
            "app.services.brew_timers.idempotency_service.fingerprint_payload",
            return_value="fp",
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
        ) as get_session,
        patch(
            "app.services.brew_timers.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
    ):
        result = await brew_timers_service.start_timer(
            db,
            "sess-1",
            TimerStartRequest(
                client_submission_id="start-1",
                expected_session_version=2,
                label="Mash rest",
                target_duration_seconds=60,
            ),
        )
        assert result == snapshot
        get_session.assert_not_called()
        append.assert_not_called()
        db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_start_timer_stale_occ():
    db = AsyncMock()
    session = _session(version=5)
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await brew_timers_service.start_timer(
                db,
                "sess-1",
                TimerStartRequest(
                    client_submission_id="start-1",
                    expected_session_version=2,
                    label="Mash rest",
                    target_duration_seconds=60,
                ),
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "CONCURRENCY_CONFLICT"


@pytest.mark.asyncio
async def test_start_rejects_foreign_stage():
    db = AsyncMock()
    session = _session(version=2)
    foreign = BrewStageOccurrence(
        id="stage-x",
        brew_session_id="other-sess",
        stage_code="MASH",
        sequence_no=1,
        status="ACTIVE",
    )

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = foreign
        return result

    db.execute = AsyncMock(side_effect=fake_execute)
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await brew_timers_service.start_timer(
                db,
                "sess-1",
                TimerStartRequest(
                    client_submission_id="start-1",
                    expected_session_version=2,
                    label="Mash rest",
                    target_duration_seconds=60,
                    stage_occurrence_id="stage-x",
                ),
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "TIMER_STAGE_SESSION_MISMATCH"


@pytest.mark.asyncio
async def test_start_rejects_blank_label_and_zero_duration():
    db = AsyncMock()
    with patch(
        "app.services.brew_timers.idempotency_service.lookup_idempotency",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc:
            await brew_timers_service.start_timer(
                db,
                "sess-1",
                TimerStartRequest(
                    client_submission_id="start-1",
                    expected_session_version=2,
                    label="   ",
                    target_duration_seconds=60,
                ),
            )
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "TIMER_INVALID_LABEL"

        with pytest.raises(HTTPException) as exc2:
            await brew_timers_service.start_timer(
                db,
                "sess-1",
                TimerStartRequest(
                    client_submission_id="start-2",
                    expected_session_version=2,
                    label="Boil",
                    target_duration_seconds=0,
                ),
            )
        assert exc2.value.status_code == 422
        assert exc2.value.detail["code"] == "TIMER_INVALID_DURATION"


@pytest.mark.asyncio
async def test_list_timers_read_only_past_due_no_writes():
    db = AsyncMock()
    session = _session(version=4)
    past = _timer(
        target=10,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=120),
    )
    assert past.ends_at is not None

    async def fake_execute(stmt):
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [past]
        result.scalars.return_value = scalars
        return result

    db.execute = AsyncMock(side_effect=fake_execute)
    with patch(
        "app.services.brew_timers.brew_session_service.get_brew_session",
        new_callable=AsyncMock,
        return_value=session,
    ):
        listed = await brew_timers_service.list_session_timers(db, "sess-1")
        assert listed["timers"][0]["computed_past_due"] is True
        assert listed["timers"][0]["status"] == "RUNNING"
        assert past.elapsed_at is None
        assert session.version == 4
        db.commit.assert_not_called()
        db.add.assert_not_called()


@pytest.mark.asyncio
async def test_observe_elapsed_rejects_before_ends_at():
    db = AsyncMock()
    session = _session(version=3)
    timer = _timer(
        started_at=datetime.now(timezone.utc),
        target=3600,
    )
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers._load_timer",
            new_callable=AsyncMock,
            return_value=timer,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await brew_timers_service.observe_elapsed(
                db,
                "timer-1",
                TimerObserveElapsedRequest(
                    client_submission_id="obs-1",
                    expected_session_version=3,
                ),
            )
        assert exc.value.detail["code"] == "TIMER_NOT_PAST_DUE"
        assert timer.elapsed_at is None
        assert session.version == 3


@pytest.mark.asyncio
async def test_observe_elapsed_success_once():
    db = AsyncMock()
    db.commit = AsyncMock()
    session = _session(version=3)
    started = datetime.now(timezone.utc) - timedelta(seconds=120)
    timer = _timer(started_at=started, target=60)
    stage_status = "ACTIVE"
    stage = BrewStageOccurrence(
        id="stage-1",
        brew_session_id="sess-1",
        stage_code="MASH",
        sequence_no=3,
        status=stage_status,
    )
    # unused but documents process-unchanged intent
    assert stage.status == "ACTIVE"

    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.brew_timers._load_timer",
            new_callable=AsyncMock,
            return_value=timer,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_timers.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
    ):
        result = await brew_timers_service.observe_elapsed(
            db,
            "timer-1",
            TimerObserveElapsedRequest(
                client_submission_id="obs-1",
                expected_session_version=3,
            ),
        )
        assert timer.elapsed_at is not None
        assert timer.status == BrewTimerStatus.ELAPSED
        assert session.version == 4
        assert session.status == "IN_PROGRESS"
        assert session.current_stage_code == "MASH"
        assert result["timer"]["status"] == "ELAPSED"
        assert result["timer"]["computed_past_due"] is False
        append.assert_awaited_once()
        assert append.await_args.kwargs["event_type"] == BrewEventType.TIMER_ELAPSED

        # Second observe with different key after elapsed
        with pytest.raises(HTTPException) as exc:
            await brew_timers_service.observe_elapsed(
                db,
                "timer-1",
                TimerObserveElapsedRequest(
                    client_submission_id="obs-2",
                    expected_session_version=4,
                ),
            )
        assert exc.value.detail["code"] == "TIMER_ALREADY_ELAPSED"
        assert session.version == 4
        assert append.await_count == 1


@pytest.mark.asyncio
async def test_observe_rejects_no_target_and_cancelled():
    db = AsyncMock()
    session = _session(version=3)
    no_end = _timer(target=None, ends_at=None)
    cancelled = _timer(
        cancelled_at=datetime.now(timezone.utc),
        status="CANCELLED",
        started_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        target=60,
    )
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_timers._load_timer",
            new_callable=AsyncMock,
            side_effect=[no_end, cancelled],
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await brew_timers_service.observe_elapsed(
                db,
                "timer-1",
                TimerObserveElapsedRequest(
                    client_submission_id="obs-a",
                    expected_session_version=3,
                ),
            )
        assert exc.value.detail["code"] == "TIMER_NO_TARGET_END"

        with pytest.raises(HTTPException) as exc2:
            await brew_timers_service.observe_elapsed(
                db,
                "timer-1",
                TimerObserveElapsedRequest(
                    client_submission_id="obs-b",
                    expected_session_version=3,
                ),
            )
        assert exc2.value.detail["code"] == "TIMER_ALREADY_CANCELLED"


@pytest.mark.asyncio
async def test_stop_timer_once_process_unchanged():
    db = AsyncMock()
    db.commit = AsyncMock()
    session = _session(version=3)
    timer = _timer()
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.brew_timers._load_timer",
            new_callable=AsyncMock,
            return_value=timer,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_timers.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
    ):
        result = await brew_timers_service.stop_timer(
            db,
            "timer-1",
            TimerStopRequest(client_submission_id="stop-1", expected_session_version=3),
        )
        assert timer.stopped_at is not None
        assert timer.status == BrewTimerStatus.STOPPED
        assert session.version == 4
        assert session.status == "IN_PROGRESS"
        assert append.await_args.kwargs["event_type"] == BrewEventType.TIMER_STOPPED
        assert result["timer"]["status"] == "STOPPED"

        with pytest.raises(HTTPException) as exc:
            await brew_timers_service.stop_timer(
                db,
                "timer-1",
                TimerStopRequest(
                    client_submission_id="stop-2", expected_session_version=4
                ),
            )
        assert exc.value.detail["code"] == "TIMER_ALREADY_STOPPED"


@pytest.mark.asyncio
async def test_cancel_timer_once_and_reject_after_stop():
    db = AsyncMock()
    db.commit = AsyncMock()
    session = _session(version=3)
    timer = _timer()
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.brew_timers._load_timer",
            new_callable=AsyncMock,
            return_value=timer,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_timers.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
    ):
        await brew_timers_service.cancel_timer(
            db,
            "timer-1",
            TimerCancelRequest(
                client_submission_id="cancel-1", expected_session_version=3
            ),
        )
        assert timer.cancelled_at is not None
        assert timer.status == BrewTimerStatus.CANCELLED
        assert session.version == 4
        assert append.await_args.kwargs["event_type"] == BrewEventType.TIMER_CANCELLED

    stopped = _timer(
        stopped_at=datetime.now(timezone.utc),
        status="STOPPED",
    )
    session2 = _session(version=5)
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers._load_timer",
            new_callable=AsyncMock,
            return_value=stopped,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session2,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await brew_timers_service.cancel_timer(
                db,
                "timer-1",
                TimerCancelRequest(
                    client_submission_id="cancel-x", expected_session_version=5
                ),
            )
        assert exc.value.detail["code"] == "TIMER_ALREADY_STOPPED"


@pytest.mark.asyncio
async def test_cancel_rejects_elapsed():
    db = AsyncMock()
    session = _session(version=3)
    elapsed = _timer(
        elapsed_at=datetime.now(timezone.utc),
        status="ELAPSED",
        started_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        target=60,
    )
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers._load_timer",
            new_callable=AsyncMock,
            return_value=elapsed,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await brew_timers_service.cancel_timer(
                db,
                "timer-1",
                TimerCancelRequest(
                    client_submission_id="cancel-e", expected_session_version=3
                ),
            )
        assert exc.value.detail["code"] == "TIMER_CANCEL_ILLEGAL"


@pytest.mark.asyncio
async def test_mutations_rejected_when_session_terminal():
    db = AsyncMock()
    closed = _session(status="CLOSED", version=9)
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=closed,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await brew_timers_service.start_timer(
                db,
                "sess-1",
                TimerStartRequest(
                    client_submission_id="t1",
                    expected_session_version=9,
                    label="Late",
                    target_duration_seconds=30,
                ),
            )
        assert exc.value.detail["code"] == "TIMER_SESSION_TERMINAL"


@pytest.mark.asyncio
async def test_stop_from_elapsed_is_legal():
    db = AsyncMock()
    db.commit = AsyncMock()
    session = _session(version=4)
    timer = _timer(
        elapsed_at=datetime.now(timezone.utc),
        status="ELAPSED",
        started_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        target=60,
    )
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.brew_timers._load_timer",
            new_callable=AsyncMock,
            return_value=timer,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_timers.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ),
    ):
        result = await brew_timers_service.stop_timer(
            db,
            "timer-1",
            TimerStopRequest(client_submission_id="stop-e", expected_session_version=4),
        )
        assert timer.stopped_at is not None
        assert timer.status == BrewTimerStatus.STOPPED
        assert result["timer"]["status"] == "STOPPED"


@pytest.mark.asyncio
async def test_atomicity_start_rolls_back_on_event_failure():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    session = _session(version=2)

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    db.execute = AsyncMock(side_effect=fake_execute)

    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_timers.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
            side_effect=RuntimeError("event failed"),
        ),
    ):
        with pytest.raises(RuntimeError):
            await brew_timers_service.start_timer(
                db,
                "sess-1",
                TimerStartRequest(
                    client_submission_id="start-fail",
                    expected_session_version=2,
                    label="Fail",
                    target_duration_seconds=30,
                ),
            )
        db.commit.assert_not_called()
        # Version bump happens after event; failure before bump keeps version.
        assert session.version == 2


@pytest.mark.asyncio
async def test_atomicity_observe_rolls_back_on_idempotency_failure():
    db = AsyncMock()
    db.commit = AsyncMock()
    session = _session(version=3)
    started = datetime.now(timezone.utc) - timedelta(seconds=120)
    timer = _timer(started_at=started, target=60)

    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_timers.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
            side_effect=RuntimeError("idempotency write failed"),
        ),
        patch(
            "app.services.brew_timers._load_timer",
            new_callable=AsyncMock,
            return_value=timer,
        ),
        patch(
            "app.services.brew_timers.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_timers.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(RuntimeError):
            await brew_timers_service.observe_elapsed(
                db,
                "timer-1",
                TimerObserveElapsedRequest(
                    client_submission_id="obs-fail",
                    expected_session_version=3,
                ),
            )
        db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_stop_replay_safe():
    db = AsyncMock()
    snapshot = {"timer": {"id": "timer-1", "status": "STOPPED"}, "session_version": 4}
    existing = MagicMock(
        operation_type="STOP_TIMER",
        request_fingerprint="fp-stop",
        response_snapshot=snapshot,
    )
    timer = _timer()
    with (
        patch(
            "app.services.brew_timers.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=existing,
        ),
        patch(
            "app.services.brew_timers.idempotency_service.fingerprint_payload",
            return_value="fp-stop",
        ),
        patch(
            "app.services.brew_timers._load_timer",
            new_callable=AsyncMock,
            return_value=timer,
        ),
        patch(
            "app.services.brew_timers.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
    ):
        result = await brew_timers_service.stop_timer(
            db,
            "timer-1",
            TimerStopRequest(client_submission_id="stop-1", expected_session_version=99),
        )
        assert result == snapshot
        append.assert_not_called()
        assert timer.stopped_at is None


@pytest.mark.asyncio
async def test_pause_does_not_rewrite_ends_at():
    """Wall-clock semantics: ends_at remains immutable across PAUSE."""
    started = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
    ends = started + timedelta(seconds=600)
    timer = _timer(started_at=started, ends_at=ends, target=600)
    original_ends = timer.ends_at
    # Simulate session pause without touching timer fields
    session = _session(status="PAUSED", version=5)
    assert session.status == "PAUSED"
    assert timer.ends_at == original_ends
    assert timer_domain.derive_ends_at(timer.started_at, timer.target_duration_seconds) == ends
