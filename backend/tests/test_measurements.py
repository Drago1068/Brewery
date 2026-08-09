"""E2A-3 measurement integrity domain and service tests."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.models import (
    BrewSession,
    BrewStageOccurrence,
    MeasurementRecord,
    MeasurementRequirement,
)
from app.domain import measurement as measurement_domain
from app.domain.enums import (
    MeasurementRequirementLevel,
    MeasurementRequirementStatus,
    MeasurementValidationClass,
)
from app.schemas.brew_day import (
    InstrumentCorrectionRequest,
    MeasurementCaptureRequest,
    MeasurementMissRequest,
    MeasurementRevisionRequest,
    MeasurementWaiveRequest,
)
from app.services import measurements as measurement_service


def test_validate_capture_input_error_non_numeric():
    result = measurement_domain.validate_capture(
        raw_value="abc",
        raw_unit="SG",
        measurement_code="OG",
        validation_min=None,
        validation_max=None,
    )
    assert result.input_error
    assert result.validation_class == MeasurementValidationClass.INPUT_ERROR


def test_validate_capture_unusual_with_bounds():
    result = measurement_domain.validate_capture(
        raw_value="80",
        raw_unit="C",
        measurement_code="MASH_TEMP",
        validation_min=Decimal("60"),
        validation_max=Decimal("72"),
    )
    assert result.ok
    assert result.validation_class == MeasurementValidationClass.UNUSUAL_VALUE


def test_validate_capture_domain_concern_sg():
    result = measurement_domain.validate_capture(
        raw_value="1.160",
        raw_unit="SG",
        measurement_code="OG",
        validation_min=None,
        validation_max=None,
    )
    # 1.160 is within structural sanity but triggers domain concern band
    assert result.ok
    assert result.validation_class == MeasurementValidationClass.DOMAIN_CONCERN


def test_planned_from_brew_plan_preserves_kind_and_absence():
    plan = {
        "planned_calculation_snapshot": {
            "results": {
                "og": {
                    "value": "1.055",
                    "unit": "SG",
                    "value_kind": "ESTIMATED",
                }
            }
        },
        "recipe_snapshot": {"recipe_version": {"batch_size": "20", "batch_size_unit": "L"}},
    }
    value, unit, kind = measurement_domain.planned_from_brew_plan(plan, "OG")
    assert value == "1.055"
    assert unit == "SG"
    assert kind == "ESTIMATED"
    absent = measurement_domain.planned_from_brew_plan(plan, "MASH_PH")
    assert absent == (None, None, None)


def test_display_value_prefers_corrected():
    record = MagicMock(corrected_value="1.052", corrected_unit="SG", raw_value="1.050", raw_unit="SG")
    assert measurement_domain.display_value(record) == ("1.052", "SG")


@pytest.mark.asyncio
async def test_capture_rejects_input_error_without_history():
    db = AsyncMock()
    session = BrewSession(
        id="sess-1",
        brew_plan_id="plan-1",
        brewery_id="b1",
        status="IN_PROGRESS",
        version=2,
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
    )
    req = MeasurementRequirement(
        id="req-1",
        brew_session_id="sess-1",
        stage_occurrence_id="stage-1",
        measurement_definition_id="def-1",
        measurement_code="OG",
        requirement_level="REQUIRED",
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    with (
        patch(
            "app.services.measurements.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.measurements.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.measurements._load_requirement",
            new_callable=AsyncMock,
            return_value=req,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await measurement_service.capture_measurement(
                db,
                "sess-1",
                MeasurementCaptureRequest(
                    client_submission_id="c1",
                    expected_session_version=2,
                    requirement_id="req-1",
                    raw_value="not-a-number",
                    raw_unit="SG",
                    confidence="HIGH",
                ),
            )
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "MEASUREMENT_INPUT_ERROR"
        db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_capture_happy_path_atomic():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    session = BrewSession(
        id="sess-1",
        brew_plan_id="plan-1",
        brewery_id="b1",
        status="IN_PROGRESS",
        version=2,
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
    )
    req = MeasurementRequirement(
        id="req-1",
        brew_session_id="sess-1",
        stage_occurrence_id="stage-1",
        measurement_definition_id="def-1",
        measurement_code="OG",
        requirement_level="REQUIRED",
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    req.record = None

    added = []

    def capture_add(obj):
        added.append(obj)
        if isinstance(obj, MeasurementRecord):
            obj.id = "rec-1"
            obj.updated_at = datetime.now(timezone.utc)
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = f"id-{len(added)}"
        if hasattr(obj, "occurred_at") and getattr(obj, "occurred_at", None) is None:
            obj.occurred_at = datetime.now(timezone.utc)

    db.add = MagicMock(side_effect=capture_add)

    with (
        patch(
            "app.services.measurements.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.measurements.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ) as record_idemp,
        patch(
            "app.services.measurements.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.measurements._load_requirement",
            new_callable=AsyncMock,
            side_effect=[req, req],
        ),
        patch(
            "app.services.measurements.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
        ) as append,
    ):
        result = await measurement_service.capture_measurement(
            db,
            "sess-1",
            MeasurementCaptureRequest(
                client_submission_id="c1",
                expected_session_version=2,
                requirement_id="req-1",
                raw_value="1.055",
                raw_unit="SG",
                confidence="HIGH",
            ),
        )
        assert req.status == MeasurementRequirementStatus.CAPTURED
        assert session.version == 3
        assert any(
            getattr(o, "event_class", None) == "RAW_CAPTURE"
            or (hasattr(o, "event_class") and str(o.event_class) == "RAW_CAPTURE")
            for o in added
        )
        append.assert_awaited()
        record_idemp.assert_awaited_once()
        db.commit.assert_awaited_once()
        assert result["session_version"] == 3


@pytest.mark.asyncio
async def test_waive_requires_reason():
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await measurement_service.waive_requirement(
            db,
            "req-1",
            MeasurementWaiveRequest(
                client_submission_id="w1",
                expected_session_version=1,
                reason="   ",
            ),
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_auto_miss_required_keeps_recommended_pending():
    db = AsyncMock()
    db.flush = AsyncMock()
    session = BrewSession(
        id="sess-1",
        brew_plan_id="plan-1",
        brewery_id="b1",
        status="IN_PROGRESS",
        version=3,
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
    )
    stage = BrewStageOccurrence(
        id="stage-1",
        brew_session_id="sess-1",
        stage_code="MASH",
        sequence_no=3,
        status="SKIPPED",
        skip_reason="time",
    )
    required = MeasurementRequirement(
        id="req-r",
        brew_session_id="sess-1",
        stage_occurrence_id="stage-1",
        measurement_definition_id="d1",
        measurement_code="MASH_TEMP",
        requirement_level=MeasurementRequirementLevel.REQUIRED,
        status=MeasurementRequirementStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    recommended = MeasurementRequirement(
        id="req-c",
        brew_session_id="sess-1",
        stage_occurrence_id="stage-1",
        measurement_definition_id="d2",
        measurement_code="MASH_PH",
        requirement_level=MeasurementRequirementLevel.RECOMMENDED,
        status=MeasurementRequirementStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )

    class Result:
        def scalars(self):
            return MagicMock(all=lambda: [required])

    db.execute = AsyncMock(return_value=Result())
    db.add = MagicMock()

    with patch(
        "app.services.measurements.brew_events_service.append_brew_event",
        new_callable=AsyncMock,
    ) as append:
        await measurement_service.auto_miss_required_for_skipped_stage(
            db,
            session=session,
            stage=stage,
            actor_id="local-brewer",
            client_submission_id="skip-1",
            client_occurred_at=None,
        )
        assert required.status == MeasurementRequirementStatus.MISSED
        assert recommended.status == MeasurementRequirementStatus.PENDING
        append.assert_awaited()


@pytest.mark.asyncio
async def test_close_gate_lists_pending_required():
    db = AsyncMock()

    class Result:
        def scalars(self):
            return MagicMock(all=lambda: ["OG", "MASH_TEMP"])

    db.execute = AsyncMock(return_value=Result())
    codes = await measurement_service.pending_required_blocks_close(db, "sess-1")
    assert codes == ["OG", "MASH_TEMP"]


@pytest.mark.asyncio
async def test_revision_requires_reason():
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await measurement_service.user_revision(
            db,
            "rec-1",
            MeasurementRevisionRequest(
                client_submission_id="r1",
                expected_session_version=1,
                raw_value="1.051",
                raw_unit="SG",
                reason="",
            ),
        )
    assert exc.value.detail["code"] == "REVISION_REASON_REQUIRED"


@pytest.mark.asyncio
async def test_atomicity_capture_rolls_back_on_brew_event_failure():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    session = BrewSession(
        id="sess-1",
        brew_plan_id="plan-1",
        brewery_id="b1",
        status="IN_PROGRESS",
        version=2,
        created_by="local-brewer",
        created_at=datetime.now(timezone.utc),
    )
    req = MeasurementRequirement(
        id="req-1",
        brew_session_id="sess-1",
        stage_occurrence_id="stage-1",
        measurement_definition_id="def-1",
        measurement_code="OG",
        requirement_level="REQUIRED",
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    req.record = None

    def add_side(obj):
        if isinstance(obj, MeasurementRecord):
            obj.id = "rec-1"
            obj.updated_at = datetime.now(timezone.utc)
        if getattr(obj, "id", None) is None and hasattr(obj, "id"):
            obj.id = "hist-1"
        if hasattr(obj, "occurred_at"):
            obj.occurred_at = datetime.now(timezone.utc)

    db.add = MagicMock(side_effect=add_side)

    with (
        patch(
            "app.services.measurements.idempotency_service.lookup_idempotency",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.measurements.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ) as record_idemp,
        patch(
            "app.services.measurements.brew_session_service.get_brew_session",
            new_callable=AsyncMock,
            return_value=session,
        ),
        patch(
            "app.services.measurements._load_requirement",
            new_callable=AsyncMock,
            return_value=req,
        ),
        patch(
            "app.services.measurements.brew_events_service.append_brew_event",
            new_callable=AsyncMock,
            side_effect=RuntimeError("event failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="event failed"):
            await measurement_service.capture_measurement(
                db,
                "sess-1",
                MeasurementCaptureRequest(
                    client_submission_id="c-fail",
                    expected_session_version=2,
                    requirement_id="req-1",
                    raw_value="1.055",
                    raw_unit="SG",
                    confidence="MEDIUM",
                ),
            )
        db.commit.assert_not_called()
        record_idemp.assert_not_called()
        assert session.version == 2
