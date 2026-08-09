"""E2A-2 transition state machine, OCC, idempotency, and atomicity tests."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.models import BrewSession, BrewStageOccurrence
from app.domain.enums import (
    BREW_DAY_STAGE_SEQUENCE,
    BrewSessionStatus,
    BrewStageCode,
    BrewStageStatus,
    BrewTransitionCommand,
)
from app.schemas.brew_day import SessionTransitionRequest
from app.services import brew_transitions as transitions
from app.services import idempotency as idempotency_service


def _stage(code: str, seq: int, status: str = "PENDING", **kwargs) -> BrewStageOccurrence:
    return BrewStageOccurrence(
        id=f"stage-{seq}",
        brew_session_id="sess-1",
        stage_code=code,
        sequence_no=seq,
        status=status,
        **kwargs,
    )


def _session(
    status: str = "PLANNED",
    version: int = 1,
    current_stage_code: str | None = None,
) -> BrewSession:
    stages = [
        _stage(code.value, i, status="PENDING")
        for i, code in enumerate(BREW_DAY_STAGE_SEQUENCE, start=1)
    ]
    session = BrewSession(
        id="sess-1",
        brew_plan_id="plan-1",
        brewery_id="brewery-1",
        status=status,
        current_stage_code=current_stage_code,
        version=version,
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
    )
    session.stage_occurrences = stages
    return session


def _req(command: str, version: int = 1, **extra) -> SessionTransitionRequest:
    return SessionTransitionRequest(
        client_submission_id="sub-1",
        expected_session_version=version,
        command=command,
        **extra,
    )


@pytest.mark.asyncio
async def test_start_session_happy_path():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    session = _session()
    with (
        patch(
            "app.services.brew_transitions.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_transitions.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ) as record,
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session_read",
            new_callable=AsyncMock,
            return_value={"id": "sess-1", "status": "IN_PROGRESS", "version": 2},
        ),
        patch(
            "app.services.brew_transitions.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
    ):
        result = await transitions.apply_transition(db, "sess-1", _req("START_SESSION"))
        assert session.status == BrewSessionStatus.IN_PROGRESS
        assert session.current_stage_code == BrewStageCode.PRE_BREW
        assert session.started_at is not None
        assert session.version == 2
        pre = next(s for s in session.stage_occurrences if s.stage_code == "PRE_BREW")
        assert pre.status == BrewStageStatus.ACTIVE
        assert pre.entered_at is not None
        assert append.await_count == 2
        types = [c.kwargs["event_type"] for c in append.await_args_list]
        assert "SESSION_STARTED" in [str(t) for t in types]
        assert "STAGE_ENTERED" in [str(t) for t in types]
        record.assert_awaited_once()
        db.commit.assert_awaited_once()
        assert result["version"] == 2


@pytest.mark.asyncio
async def test_start_session_rejects_when_not_planned():
    db = AsyncMock()
    session = _session(status="IN_PROGRESS", version=2, current_stage_code="PRE_BREW")
    with (
        patch(
            "app.services.brew_transitions.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await transitions.apply_transition(db, "sess-1", _req("START_SESSION", version=2))
        assert exc.value.detail["code"] == "ILLEGAL_TRANSITION"


@pytest.mark.asyncio
async def test_concurrency_conflict():
    db = AsyncMock()
    session = _session(version=3)
    with (
        patch(
            "app.services.brew_transitions.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await transitions.apply_transition(db, "sess-1", _req("START_SESSION", version=1))
        assert exc.value.detail["code"] == "CONCURRENCY_CONFLICT"


@pytest.mark.asyncio
async def test_idempotent_replay_skips_mutation():
    db = AsyncMock()
    original = {"id": "sess-1", "version": 2, "status": "IN_PROGRESS"}
    existing = MagicMock()
    existing.operation_type = "START_SESSION"
    existing.request_fingerprint = idempotency_service.fingerprint_payload(
        {
            "command": "START_SESSION",
            "skip_reason": None,
            "abort_reason": None,
            "client_occurred_at": None,
        }
    )
    existing.response_snapshot = original
    with patch(
        "app.services.brew_transitions.idempotency_service.lookup_idempotency",
        new_callable=AsyncMock,
        return_value=existing,
    ):
        result = await transitions.apply_transition(db, "sess-1", _req("START_SESSION"))
        assert result == original
        db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_advance_illegal_while_paused():
    db = AsyncMock()
    session = _session(status="PAUSED", version=2, current_stage_code="PRE_BREW")
    session.stage_occurrences[0].status = BrewStageStatus.ACTIVE
    with (
        patch(
            "app.services.brew_transitions.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await transitions.apply_transition(db, "sess-1", _req("ADVANCE_STAGE", version=2))
        assert exc.value.detail["code"] == "SESSION_PAUSED"


@pytest.mark.asyncio
async def test_skip_requires_reason():
    db = AsyncMock()
    session = _session(status="IN_PROGRESS", version=2, current_stage_code="PRE_BREW")
    session.stage_occurrences[0].status = BrewStageStatus.ACTIVE
    with (
        patch(
            "app.services.brew_transitions.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await transitions.apply_transition(db, "sess-1", _req("SKIP_STAGE", version=2))
        assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_advance_completes_and_enters_next():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    session = _session(status="IN_PROGRESS", version=2, current_stage_code="PRE_BREW")
    session.stage_occurrences[0].status = BrewStageStatus.ACTIVE
    session.stage_occurrences[0].entered_at = datetime.now(timezone.utc)
    with (
        patch(
            "app.services.brew_transitions.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_transitions.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session_read",
            new_callable=AsyncMock,
            return_value={"id": "sess-1", "version": 3},
        ),
        patch(
            "app.services.brew_transitions.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
    ):
        await transitions.apply_transition(db, "sess-1", _req("ADVANCE_STAGE", version=2))
        assert session.stage_occurrences[0].status == BrewStageStatus.COMPLETED
        assert session.stage_occurrences[1].status == BrewStageStatus.ACTIVE
        assert session.current_stage_code == "MASH_IN"
        assert session.version == 3
        assert append.await_count == 2


@pytest.mark.asyncio
async def test_pause_resume_abort_close_matrix():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    async def run(session, command, version, **extra):
        with (
            patch(
                "app.services.brew_transitions.idempotency_service.lookup_idempotency",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.brew_transitions.idempotency_service.record_idempotency",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.brew_transitions.brew_session_service.get_brew_session",
                new_callable=AsyncMock,
                return_value=session,
            ),
            patch(
                "app.services.brew_transitions.brew_session_service.get_brew_session_read",
                new_callable=AsyncMock,
                return_value={"id": "sess-1", "version": version + 1},
            ),
            patch(
                "app.services.brew_transitions.brew_events_service.append_brew_event",
                new_callable=AsyncMock,
            ),
        ):
            return await transitions.apply_transition(
                db, "sess-1", _req(command, version=version, **extra)
            )

    session = _session(status="IN_PROGRESS", version=2, current_stage_code="PRE_BREW")
    session.stage_occurrences[0].status = BrewStageStatus.ACTIVE
    await run(session, "PAUSE_SESSION", 2)
    assert session.status == BrewSessionStatus.PAUSED
    assert session.version == 3

    await run(session, "RESUME_SESSION", 3)
    assert session.status == BrewSessionStatus.IN_PROGRESS

    await run(session, "ABORT_SESSION", 4, abort_reason="equipment failure")
    assert session.status == BrewSessionStatus.ABORTED
    assert session.abort_reason == "equipment failure"

    with pytest.raises(HTTPException) as exc:
        await run(session, "RESUME_SESSION", 5)
    assert exc.value.detail["code"] == "SESSION_TERMINAL"


@pytest.mark.asyncio
async def test_close_illegal_while_paused():
    db = AsyncMock()
    session = _session(status="PAUSED", version=2, current_stage_code="PRE_BREW")
    with (
        patch(
            "app.services.brew_transitions.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await transitions.apply_transition(db, "sess-1", _req("CLOSE_SESSION", version=2))
        assert exc.value.detail["code"] == "SESSION_PAUSED"


@pytest.mark.asyncio
async def test_atomicity_rolls_back_when_brew_event_fails():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    session = _session()

    async def fail_append(*args, **kwargs):
        raise RuntimeError("brew_event write failed")

    with (
        patch(
            "app.services.brew_transitions.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_transitions.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ) as record,
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_transitions.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
            side_effect=fail_append,
        ),
    ):
        with pytest.raises(RuntimeError, match="brew_event write failed"):
            await transitions.apply_transition(db, "sess-1", _req("START_SESSION"))
        db.commit.assert_not_called()
        record.assert_not_called()
        # Domain mutations happened in memory before event failure; without commit
        # they are not durable — assert command aborted before idempotency/commit.
        assert session.version == 1 or session.version == 2
        # Version bump happens after events; failure during first event keeps version 1.
        assert session.version == 1


@pytest.mark.asyncio
async def test_skip_measurement_hook_auto_misses():
    db = AsyncMock()
    session = _session(status="IN_PROGRESS")
    stage = session.stage_occurrences[0]
    with patch(
        "app.services.brew_transitions.measurement_service.auto_miss_required_for_skipped_stage",
        new_callable=AsyncMock,
    ) as auto_miss:
        await transitions.apply_skip_measurement_side_effects(
            db,
            session=session,
            stage=stage,
            actor_id="local-brewer",
            client_submission_id="s1",
        )
        auto_miss.assert_awaited_once()


@pytest.mark.asyncio
async def test_resume_requires_paused():
    db = AsyncMock()
    session = _session(status="IN_PROGRESS", version=2)
    with (
        patch(
            "app.services.brew_transitions.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.brew_transitions.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await transitions.apply_transition(db, "sess-1", _req("RESUME_SESSION", version=2))
        assert exc.value.detail["code"] == "ILLEGAL_TRANSITION"


@pytest.mark.asyncio
async def test_idempotency_conflict_different_body():
    db = AsyncMock()
    existing = MagicMock()
    existing.operation_type = "START_SESSION"
    existing.request_fingerprint = "other"
    existing.resource_type = "BrewSession"
    existing.resource_id = "sess-1"
    with patch(
        "app.services.brew_transitions.idempotency_service.lookup_idempotency",
        new_callable=AsyncMock,
        return_value=existing,
    ):
        with pytest.raises(HTTPException) as exc:
            await transitions.apply_transition(db, "sess-1", _req("START_SESSION"))
        assert exc.value.detail["code"] == "IDEMPOTENCY_CONFLICT"
