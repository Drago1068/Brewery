"""E2A-5 fermentation handoff eligibility, honesty, OCC, and atomicity tests."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.models import BrewPlan, BrewSession, FermentationHandoff
from app.domain.enums import BrewEventType, BrewSessionStatus
from app.schemas.brew_day import FermentationHandoffRequest
from app.services import fermentation_handoff as handoff_service


def _session(status: str = "CLOSED", version: int = 12) -> BrewSession:
    return BrewSession(
        id="sess-1",
        brew_plan_id="plan-1",
        brewery_id="brewery-1",
        status=status,
        version=version,
        closed_at=datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc),
        created_by="local-brewer",
        created_at=datetime(2026, 8, 9, 9, 0, tzinfo=timezone.utc),
    )


def _plan() -> BrewPlan:
    return BrewPlan(
        id="plan-1",
        brewery_id="brewery-1",
        recipe_id="recipe-1",
        recipe_version_id="rv-1",
        status="CREATED",
        batch_size="20",
        batch_size_unit="L",
        recipe_snapshot={
            "name": "IPA",
            "ingredients": [{"ingredient_type": "YEAST", "name": "US-05"}],
        },
        planned_calculation_snapshot={},
        readiness_status="GREEN",
        readiness_summary="ok",
        readiness_checks_snapshot=[],
        readiness_acknowledged=False,
        created_by="local-brewer",
        created_at=datetime(2026, 8, 9, 8, 0, tzinfo=timezone.utc),
    )


def _requirements_measured_og():
    return [
        {
            "id": "req-og",
            "measurement_code": "OG",
            "requirement_level": "REQUIRED",
            "status": "CAPTURED",
            "planned_value": "1.054",
            "planned_unit": "SG",
            "planned_kind": "ESTIMATED",
            "record": {
                "id": "rec-og",
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
            "status": "CAPTURED",
            "planned_value": "20",
            "planned_unit": "L",
            "planned_kind": "PLANNED",
            "record": {
                "id": "rec-vol",
                "display_value": "19.5",
                "display_unit": "L",
                "value_kind": "MEASURED",
                "confidence": "MEDIUM",
                "raw_value": "19.5",
                "corrected_value": None,
            },
        },
        {
            "id": "req-pitch",
            "measurement_code": "YEAST_PITCH_TEMP",
            "requirement_level": "REQUIRED",
            "status": "PENDING",
            "planned_value": None,
            "planned_unit": None,
            "planned_kind": None,
            "record": None,
        },
    ]


def _report_stub():
    return {
        "deviations_and_warnings": [{"type": "MEASUREMENT_MISSED", "measurement_code": "KNOCKOUT_TEMP"}],
        "data_completeness": {"required": {"captured": 2, "missed": 1, "pending": 1}},
        "process_adherence": {
            "stages_completed": 8,
            "stages_skipped": 1,
            "skipped_stages": [{"stage_code": "MASH", "skip_reason": "x"}],
        },
        "measurement_quality": [
            {
                "measurement_code": "OG",
                "requirement_id": "req-og",
                "requirement_status": "CAPTURED",
                "confidence": "HIGH",
                "history": {"latest_observation_history_id": "obs-1"},
            }
        ],
    }


@pytest.mark.asyncio
async def test_handoff_closed_only_success_and_honesty():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    session = _session()
    plan = _plan()

    async def fake_execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        if "fermentation_handoffs" in sql.lower() or "FermentationHandoff" in sql:
            result.scalar_one_or_none.return_value = None
            return result
        result.scalar_one.return_value = plan
        return result

    db.execute = AsyncMock(side_effect=fake_execute)

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
            return_value=_requirements_measured_og(),
        ),
        patch(
            "app.services.fermentation_handoff.report_service.build_brew_day_report",
            new_callable=AsyncMock,
            return_value=_report_stub(),
        ),
        patch(
            "app.services.fermentation_handoff.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
    ):
        result = await handoff_service.create_fermentation_handoff(
            db,
            "sess-1",
            FermentationHandoffRequest(
                client_submission_id="ho-1", expected_session_version=12
            ),
        )
        assert session.status == BrewSessionStatus.HANDED_OFF
        assert session.version == 13
        payload = result["handoff"]["payload"]
        assert payload["boundary"]["claims_fermentation_readiness"] is False
        og = payload["measurements"]["og"]
        assert og["planned"]["kind"] == "ESTIMATED"
        assert og["actual"]["kind"] == "MEASURED"
        assert og["actual"]["value"] == "1.056"
        assert payload["measurements"]["knockout_temp"]["actual"]["status"] == "MISSED"
        assert payload["measurements"]["yeast_pitch_temp"]["actual"]["value"] is None
        append.assert_awaited_once()
        assert append.await_args.kwargs["event_type"] == BrewEventType.FERMENTATION_HANDOFF_CREATED
        db.commit.assert_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        ("ABORTED", "SESSION_ABORTED_NO_HANDOFF"),
        ("IN_PROGRESS", "SESSION_NOT_CLOSED_FOR_HANDOFF"),
        ("PAUSED", "SESSION_NOT_CLOSED_FOR_HANDOFF"),
        ("PLANNED", "SESSION_NOT_CLOSED_FOR_HANDOFF"),
        ("HANDED_OFF", "FERMENTATION_HANDOFF_ALREADY_EXISTS"),
    ],
)
async def test_handoff_rejects_non_closed(status, code):
    db = AsyncMock()
    session = _session(status=status, version=5)
    with (
        patch(
            "app.services.fermentation_handoff.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.fermentation_handoff.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await handoff_service.create_fermentation_handoff(
                db,
                "sess-1",
                FermentationHandoffRequest(
                    client_submission_id=f"ho-{status}", expected_session_version=5
                ),
            )
        assert exc.value.detail["code"] == code


@pytest.mark.asyncio
async def test_handoff_idempotent_replay_after_handed_off():
    db = AsyncMock()
    snapshot = {
        "handoff": {"id": "ho-row"},
        "session_status": "HANDED_OFF",
        "session_version": 13,
    }
    existing = MagicMock(
        operation_type="CREATE_FERMENTATION_HANDOFF",
        request_fingerprint="fp",
        response_snapshot=snapshot,
    )
    with (
        patch(
            "app.services.fermentation_handoff.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=existing,
        ),
        patch(
            "app.services.fermentation_handoff.idempotency_service.fingerprint_payload",
            return_value="fp",
        ),
        patch(
            "app.services.fermentation_handoff.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
    ):
        result = await handoff_service.create_fermentation_handoff(
            db,
            "sess-1",
            FermentationHandoffRequest(
                client_submission_id="ho-1", expected_session_version=99
            ),
        )
        assert result == snapshot
        append.assert_not_called()


@pytest.mark.asyncio
async def test_handoff_stale_occ():
    db = AsyncMock()
    session = _session(version=20)
    with (
        patch(
            "app.services.fermentation_handoff.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.fermentation_handoff.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await handoff_service.create_fermentation_handoff(
                db,
                "sess-1",
                FermentationHandoffRequest(
                    client_submission_id="ho-stale", expected_session_version=12
                ),
            )
        assert exc.value.detail["code"] == "CONCURRENCY_CONFLICT"


@pytest.mark.asyncio
async def test_handoff_atomicity_rolls_back_on_event_failure():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    session = _session()
    plan = _plan()

    async def fake_execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        if "FermentationHandoff" in sql or "fermentation_handoffs" in sql.lower():
            result.scalar_one_or_none.return_value = None
            return result
        result.scalar_one.return_value = plan
        return result

    db.execute = AsyncMock(side_effect=fake_execute)
    with (
        patch(
            "app.services.fermentation_handoff.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.fermentation_handoff.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.fermentation_handoff.measurement_service.list_session_requirements",
            new_callable=AsyncMock,
            return_value=_requirements_measured_og(),
        ),
        patch(
            "app.services.fermentation_handoff.report_service.build_brew_day_report",
            new_callable=AsyncMock,
            return_value=_report_stub(),
        ),
        patch(
            "app.services.fermentation_handoff.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
            side_effect=RuntimeError("event failed"),
        ),
    ):
        with pytest.raises(RuntimeError):
            await handoff_service.create_fermentation_handoff(
                db,
                "sess-1",
                FermentationHandoffRequest(
                    client_submission_id="ho-fail", expected_session_version=12
                ),
            )
        db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_second_handoff_conflict_when_row_exists():
    db = AsyncMock()
    session = _session(status="CLOSED", version=12)
    existing = FermentationHandoff(
        id="existing",
        brewery_id="brewery-1",
        brew_session_id="sess-1",
        brew_plan_id="plan-1",
        recipe_version_id="rv-1",
        client_submission_id="old",
        created_by="local-brewer",
        payload={},
    )

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        return result

    db.execute = AsyncMock(side_effect=fake_execute)
    with (
        patch(
            "app.services.fermentation_handoff.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.fermentation_handoff.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await handoff_service.create_fermentation_handoff(
                db,
                "sess-1",
                FermentationHandoffRequest(
                    client_submission_id="ho-2", expected_session_version=12
                ),
            )
        assert exc.value.detail["code"] == "FERMENTATION_HANDOFF_ALREADY_EXISTS"
