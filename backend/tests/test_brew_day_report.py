"""E2A-5 Brew-Day report and planned-vs-actual domain tests."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import BrewPlan, BrewSession, BrewStageOccurrence
from app.domain.brew_day_report import compare_planned_actual
from app.domain.enums import BrewSessionStatus, BrewStageStatus
from app.services import brew_day_report as report_service


def test_compare_valid_pair_same_unit():
    result = compare_planned_actual(
        planned_value="1.054",
        planned_unit="SG",
        planned_kind="ESTIMATED",
        actual_value="1.056",
        actual_unit="SG",
        actual_kind="MEASURED",
        requirement_status="CAPTURED",
    )
    assert result["comparison_available"] is True
    assert result["delta"] == "0.002"
    assert result["percent_delta"] is not None


def test_compare_missing_actual_no_delta():
    result = compare_planned_actual(
        planned_value="1.054",
        planned_unit="SG",
        planned_kind="ESTIMATED",
        actual_value=None,
        actual_unit=None,
        actual_kind=None,
        requirement_status="MISSED",
    )
    assert result["comparison_available"] is False
    assert result["delta"] is None
    assert result["unavailable_reason"] == "ACTUAL_MISSING"


def test_compare_incompatible_units():
    result = compare_planned_actual(
        planned_value="20",
        planned_unit="L",
        planned_kind="PLANNED",
        actual_value="68",
        actual_unit="F",
        actual_kind="MEASURED",
        requirement_status="CAPTURED",
    )
    assert result["comparison_available"] is False
    assert result["unavailable_reason"] == "INCOMPATIBLE_UNITS"


def test_compare_volume_conversion():
    result = compare_planned_actual(
        planned_value="20",
        planned_unit="L",
        planned_kind="PLANNED",
        actual_value="5",
        actual_unit="gal",
        actual_kind="MEASURED",
        requirement_status="CAPTURED",
    )
    assert result["comparison_available"] is True
    assert result["comparison_unit"] == "L"
    assert result["conversion_formula_id"] == "UNIT_CONVERSION"


def _session_with_stages(status="CLOSED") -> BrewSession:
    session = BrewSession(
        id="sess-1",
        brew_plan_id="plan-1",
        brewery_id="brewery-1",
        status=status,
        current_stage_code=None,
        version=10,
        started_at=datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc),
        closed_at=datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc),
        abort_reason=None,
        created_by="local-brewer",
        created_at=datetime(2026, 8, 9, 9, 0, tzinfo=timezone.utc),
    )
    session.stage_occurrences = [
        BrewStageOccurrence(
            id="st-1",
            brew_session_id="sess-1",
            stage_code="PRE_BREW",
            sequence_no=1,
            status=BrewStageStatus.COMPLETED,
        ),
        BrewStageOccurrence(
            id="st-2",
            brew_session_id="sess-1",
            stage_code="MASH",
            sequence_no=2,
            status=BrewStageStatus.SKIPPED,
            skip_reason="equipment constraint",
        ),
    ]
    return session


def _plan() -> BrewPlan:
    return BrewPlan(
        id="plan-1",
        brewery_id="brewery-1",
        recipe_id="recipe-1",
        recipe_version_id="rv-1",
        status="CREATED",
        batch_size="20",
        batch_size_unit="L",
        recipe_snapshot={"name": "Test IPA", "recipe_version": {"id": "rv-1"}},
        planned_calculation_snapshot={"results": {"og": {"value": "1.054", "unit": "SG"}}},
        readiness_status="YELLOW",
        readiness_summary="inventory caution",
        readiness_checks_snapshot=[{"code": "INV", "severity": "WARNING"}],
        readiness_acknowledged=True,
        readiness_acknowledged_at=datetime(2026, 8, 9, 8, 0, tzinfo=timezone.utc),
        readiness_acknowledged_by="local-brewer",
        readiness_acknowledgement_note="proceeding cautiously",
        created_by="local-brewer",
        created_at=datetime(2026, 8, 9, 8, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_report_read_only_structure_and_no_score():
    db = AsyncMock()
    session = _session_with_stages()
    plan = _plan()
    requirements = [
        {
            "id": "req-og",
            "measurement_code": "OG",
            "requirement_level": "REQUIRED",
            "status": "CAPTURED",
            "stage_occurrence_id": "st-x",
            "planned_value": "1.054",
            "planned_unit": "SG",
            "planned_kind": "ESTIMATED",
            "record": {
                "id": "rec-1",
                "display_value": "1.056",
                "display_unit": "SG",
                "value_kind": "MEASURED",
                "confidence": "HIGH",
                "instrument": "refractometer",
                "method": None,
                "provenance": {"source": "brewer"},
                "validation_class": "OK",
                "validation_notes": None,
                "raw_value": "1.055",
                "raw_unit": "SG",
                "corrected_value": "1.056",
                "corrected_unit": "SG",
            },
        },
        {
            "id": "req-ph",
            "measurement_code": "MASH_PH",
            "requirement_level": "RECOMMENDED",
            "status": "PENDING",
            "stage_occurrence_id": "st-2",
            "planned_value": None,
            "planned_unit": None,
            "planned_kind": None,
            "record": None,
        },
        {
            "id": "req-vol",
            "measurement_code": "POST_BOIL_VOLUME",
            "requirement_level": "REQUIRED",
            "status": "MISSED",
            "stage_occurrence_id": "st-x",
            "planned_value": "20",
            "planned_unit": "L",
            "planned_kind": "PLANNED",
            "record": None,
        },
    ]

    async def fake_execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        if "brew_plans" in sql.lower() or "BrewPlan" in sql:
            result.scalar_one.return_value = plan
            return result
        if "brew_events" in sql.lower() or "BrewEvent" in sql:
            scalars = MagicMock()
            scalars.all.return_value = []
            result.scalars.return_value = scalars
            return result
        scalars = MagicMock()
        obs = MagicMock(
            event_class="RAW_CAPTURE",
            id="obs-1",
            raw_value="1.055",
            raw_unit="SG",
        )
        obs2 = MagicMock(
            event_class="INSTRUMENT_CORRECTION",
            id="obs-2",
            raw_value=None,
            raw_unit=None,
        )
        scalars.all.return_value = [obs, obs2]
        result.scalars.return_value = scalars
        return result

    db.execute = AsyncMock(side_effect=fake_execute)

    with (
        patch(
            "app.services.brew_day_report.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_day_report.measurement_service.list_session_requirements",
            new_callable=AsyncMock,
            return_value=requirements,
        ),
        patch(
            "app.services.brew_day_report.brew_timers_service.list_session_timers",
            new_callable=AsyncMock,
            return_value={
                "brew_session_id": "sess-1",
                "timers": [
                    {
                        "id": "t1",
                        "label": "Mash",
                        "target_duration_seconds": 60,
                        "started_at": "2026-08-09T11:00:00+00:00",
                        "ends_at": "2026-08-09T11:01:00+00:00",
                        "elapsed_at": "2026-08-09T11:01:05+00:00",
                        "stopped_at": None,
                        "cancelled_at": None,
                        "status": "ELAPSED",
                        "computed_past_due": False,
                        "stage_occurrence_id": "st-2",
                    }
                ],
            },
        ),
    ):
        report = await report_service.build_brew_day_report(db, "sess-1")
        assert report["overall_brew_score"] is None
        assert report["dimensions_are_independent"] is True
        assert "Brew Score" not in str(report)
        assert report["data_completeness"]["required"]["captured"] == 1
        assert report["data_completeness"]["required"]["missed"] == 1
        assert report["data_completeness"]["recommended"]["pending"] == 1
        assert report["process_adherence"]["stages_skipped"] == 1
        assert report["process_adherence"]["skipped_stages"][0]["skip_reason"] == (
            "equipment constraint"
        )
        og_cmp = next(c for c in report["planned_vs_actual"] if c["measurement_code"] == "OG")
        assert og_cmp["comparison_available"] is True
        missed = next(
            c
            for c in report["planned_vs_actual"]
            if c["measurement_code"] == "POST_BOIL_VOLUME"
        )
        assert missed["delta"] is None
        quality = next(q for q in report["measurement_quality"] if q["measurement_code"] == "OG")
        assert quality["correction_present"] is True
        assert quality["history"]["has_raw_capture"] is True
        assert quality["history"]["has_instrument_correction"] is True
        assert quality["confidence"] == "HIGH"
        assert report["timer_evidence"][0]["status"] == "ELAPSED"
        assert report["readiness_acknowledgement"]["readiness_status"] == "YELLOW"
        assert report["readiness_acknowledgement"]["reinterpreted_as_green"] is False
        assert any(d["type"] == "STAGE_SKIPPED" for d in report["deviations_and_warnings"])
        assert any(
            d["type"] == "READINESS_ACKNOWLEDGED" for d in report["deviations_and_warnings"]
        )
        db.commit.assert_not_called()
        db.add.assert_not_called()


@pytest.mark.asyncio
async def test_aborted_session_report_classification():
    db = AsyncMock()
    session = _session_with_stages(status=BrewSessionStatus.ABORTED)
    session.abort_reason = "stuck mash"
    plan = _plan()

    async def fake_execute(stmt):
        result = MagicMock()
        sql = str(stmt)
        if "BrewPlan" in sql or "brew_plans" in sql.lower():
            result.scalar_one.return_value = plan
            return result
        scalars = MagicMock()
        scalars.all.return_value = []
        result.scalars.return_value = scalars
        return result

    db.execute = AsyncMock(side_effect=fake_execute)
    with (
        patch(
            "app.services.brew_day_report.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.brew_day_report.measurement_service.list_session_requirements",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.services.brew_day_report.brew_timers_service.list_session_timers",
            new_callable=AsyncMock,
            return_value={"brew_session_id": "sess-1", "timers": []},
        ),
    ):
        report = await report_service.build_brew_day_report(db, "sess-1")
        assert report["session_summary"]["report_classification"] == "ABORTED_INCOMPLETE"
        assert any(d["type"] == "SESSION_ABORTED" for d in report["deviations_and_warnings"])
