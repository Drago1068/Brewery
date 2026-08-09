"""Canonical Epic 2A backend journey (E2A-5) — mocked service orchestration.

Covers plan→session→start→measure→timer→report→close→handoff without DB.
Live Docker persistence is verified separately via migration scripts.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import BrewPlan, BrewSession, BrewStageOccurrence, BrewTimer
from app.domain.enums import (
    BREW_DAY_STAGE_SEQUENCE,
    BrewSessionStatus,
    BrewStageStatus,
)
from app.schemas.brew_day import (
    FermentationHandoffRequest,
    TimerObserveElapsedRequest,
    TimerStartRequest,
)
from app.schemas.brew_day import SessionTransitionRequest
from app.services import brew_day_report as report_service
from app.services import brew_timers as brew_timers_service
from app.services import brew_transitions as transitions
from app.services import fermentation_handoff as handoff_service


def _stages(session_id: str = "sess-1") -> list[BrewStageOccurrence]:
    return [
        BrewStageOccurrence(
            id=f"stage-{i}",
            brew_session_id=session_id,
            stage_code=code.value,
            sequence_no=i,
            status=BrewStageStatus.PENDING,
        )
        for i, code in enumerate(BREW_DAY_STAGE_SEQUENCE, start=1)
    ]


@pytest.mark.asyncio
async def test_canonical_e2a_backend_journey_close_report_handoff():
    """ACTIVE path → start → close (no auto handoff) → report → explicit handoff."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    session = BrewSession(
        id="sess-1",
        brew_plan_id="plan-1",
        brewery_id="brewery-1",
        status=BrewSessionStatus.PLANNED,
        version=1,
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
    )
    session.stage_occurrences = _stages()

    # START
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
            return_value={"id": "sess-1", "status": "IN_PROGRESS", "version": 2},
        ),
        patch(
            "app.services.brew_transitions.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ),
    ):
        await transitions.apply_transition(
            db,
            "sess-1",
            SessionTransitionRequest(
                client_submission_id="start-1",
                expected_session_version=1,
                command="START_SESSION",
            ),
        )
    assert session.status == BrewSessionStatus.IN_PROGRESS
    assert session.version == 2

    # Timer start + observe-elapsed (informational only)
    started = datetime.now(timezone.utc) - timedelta(seconds=120)
    timer = BrewTimer(
        id="timer-1",
        brewery_id="brewery-1",
        brew_session_id="sess-1",
        label="Mash rest",
        target_duration_seconds=60,
        started_at=started,
        ends_at=started + timedelta(seconds=60),
        status="RUNNING",
        start_client_submission_id="timer-start",
        created_by="local-brewer",
        created_at=started,
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
        await brew_timers_service.observe_elapsed(
            db,
            "timer-1",
            TimerObserveElapsedRequest(
                client_submission_id="obs-1", expected_session_version=2
            ),
        )
    assert timer.status == "ELAPSED"
    assert session.status == BrewSessionStatus.IN_PROGRESS  # timer never drives process
    assert session.version == 3

    # CLOSE — no auto handoff
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
            return_value={"id": "sess-1", "status": "CLOSED", "version": 4},
        ),
        patch(
            "app.services.brew_transitions.measurement_service.pending_required_blocks_close",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.services.brew_transitions.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as close_append,
    ):
        await transitions.apply_transition(
            db,
            "sess-1",
            SessionTransitionRequest(
                client_submission_id="close-1",
                expected_session_version=3,
                command="CLOSE_SESSION",
            ),
        )
    assert session.status == BrewSessionStatus.CLOSED
    assert close_append.await_args.kwargs["payload"]["fermentation_handoff_created"] is False

    # Report after close
    plan = BrewPlan(
        id="plan-1",
        brewery_id="brewery-1",
        recipe_id="r1",
        recipe_version_id="rv1",
        status="CREATED",
        batch_size="20",
        batch_size_unit="L",
        recipe_snapshot={"name": "IPA"},
        planned_calculation_snapshot={},
        readiness_status="GREEN",
        readiness_summary="ok",
        readiness_checks_snapshot=[],
        readiness_acknowledged=False,
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
    )

    async def report_execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        if "BrewPlan" in sql or "brew_plans" in sql.lower():
            result.scalar_one.return_value = plan
            return result
        scalars = MagicMock()
        scalars.all.return_value = []
        result.scalars.return_value = scalars
        return result

    db.execute = AsyncMock(side_effect=report_execute)
    with (
        patch(
            "app.services.brew_day_report.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_day_report.measurement_service.list_session_requirements",
            new_callable=AsyncMock,
            return_value=[
                {
                    "id": "req-og",
                    "measurement_code": "OG",
                    "requirement_level": "REQUIRED",
                    "status": "CAPTURED",
                    "stage_occurrence_id": None,
                    "planned_value": "1.054",
                    "planned_unit": "SG",
                    "planned_kind": "ESTIMATED",
                    "record": {
                        "id": "rec",
                        "display_value": "1.056",
                        "display_unit": "SG",
                        "value_kind": "MEASURED",
                        "confidence": "HIGH",
                        "instrument": None,
                        "method": None,
                        "provenance": None,
                        "validation_class": "OK",
                        "validation_notes": None,
                        "raw_value": "1.056",
                        "raw_unit": "SG",
                        "corrected_value": None,
                        "corrected_unit": None,
                    },
                }
            ],
        ),
        patch(
            "app.services.brew_day_report.brew_timers_service.list_session_timers",
            new_callable=AsyncMock,
            return_value={
                "timers": [
                    {
                        "id": "timer-1",
                        "label": "Mash rest",
                        "status": "ELAPSED",
                        "target_duration_seconds": 60,
                        "started_at": started.isoformat(),
                        "ends_at": (started + timedelta(seconds=60)).isoformat(),
                        "elapsed_at": timer.elapsed_at.isoformat() if timer.elapsed_at else None,
                        "stopped_at": None,
                        "cancelled_at": None,
                        "computed_past_due": False,
                        "stage_occurrence_id": None,
                    }
                ]
            },
        ),
    ):
        report = await report_service.build_brew_day_report(db, "sess-1")
    assert report["overall_brew_score"] is None
    assert report["session_summary"]["report_classification"] == "CLOSED"
    assert report["timer_evidence"][0]["status"] == "ELAPSED"
    assert report["data_completeness"]["required"]["captured"] == 1

    # Explicit handoff
    async def handoff_execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        if "FermentationHandoff" in sql or "fermentation_handoffs" in sql.lower():
            result.scalar_one_or_none.return_value = None
            return result
        result.scalar_one.return_value = plan
        return result

    db.execute = AsyncMock(side_effect=handoff_execute)
    with (
        patch(
            "app.services.fermentation_handoff.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.fermentation_handoff.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.fermentation_handoff.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.fermentation_handoff.measurement_service.list_session_requirements",
            new_callable=AsyncMock,
            return_value=[
                {
                    "id": "req-og",
                    "measurement_code": "OG",
                    "requirement_level": "REQUIRED",
                    "status": "CAPTURED",
                    "planned_value": "1.054",
                    "planned_unit": "SG",
                    "planned_kind": "ESTIMATED",
                    "record": {
                        "id": "rec",
                        "display_value": "1.056",
                        "display_unit": "SG",
                        "value_kind": "MEASURED",
                        "confidence": "HIGH",
                        "raw_value": "1.056",
                        "corrected_value": None,
                    },
                },
                {
                    "id": "req-ko",
                    "measurement_code": "KNOCKOUT_TEMP",
                    "requirement_level": "REQUIRED",
                    "status": "MISSED",
                    "planned_value": None,
                    "planned_unit": None,
                    "planned_kind": None,
                    "record": None,
                },
                {
                    "id": "req-vol",
                    "measurement_code": "POST_BOIL_VOLUME",
                    "requirement_level": "REQUIRED",
                    "status": "WAIVED",
                    "planned_value": "20",
                    "planned_unit": "L",
                    "planned_kind": "PLANNED",
                    "record": None,
                },
                {
                    "id": "req-yp",
                    "measurement_code": "YEAST_PITCH_TEMP",
                    "requirement_level": "REQUIRED",
                    "status": "CAPTURED",
                    "planned_value": None,
                    "planned_unit": None,
                    "planned_kind": None,
                    "record": {
                        "id": "rec-yp",
                        "display_value": "18",
                        "display_unit": "C",
                        "value_kind": "MEASURED",
                        "confidence": "MEDIUM",
                        "raw_value": "18",
                        "corrected_value": None,
                    },
                },
            ],
        ),
        patch(
            "app.services.fermentation_handoff.report_service.build_brew_day_report",
            new_callable=AsyncMock,
            return_value=report,
        ),
        patch(
            "app.services.fermentation_handoff.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ),
    ):
        handoff = await handoff_service.create_fermentation_handoff(
            db,
            "sess-1",
            FermentationHandoffRequest(
                client_submission_id="handoff-1",
                expected_session_version=4,
            ),
        )
    assert session.status == BrewSessionStatus.HANDED_OFF
    assert handoff["session_status"] == "HANDED_OFF"
    og = handoff["handoff"]["payload"]["measurements"]["og"]
    assert og["planned"]["kind"] == "ESTIMATED"
    assert og["actual"]["kind"] == "MEASURED"
    assert og["actual"]["value"] == "1.056"
    assert handoff["handoff"]["payload"]["boundary"]["claims_fermentation_readiness"] is False
