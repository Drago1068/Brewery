"""Service-level BrewPlan readiness and idempotency behavior (mocked DB collaborators)."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.models import BrewPlan, IdempotencyRecord
from app.schemas.brew_day import BrewPlanCreate, ReadinessAcknowledgement
from app.services import brew_plan as brew_plan_service
from app.services import idempotency as idempotency_service


def _version(status="ACTIVE"):
    v = MagicMock()
    v.id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    v.recipe_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    v.status = status
    v.batch_size = Decimal("5")
    v.batch_size_unit = "gal"
    v.brewhouse_efficiency = Decimal("72")
    v.equipment_profile_id = None
    v.boil_time_minutes = 60
    v.mash_method = "SINGLE_INFUSION"
    v.notes = None
    v.change_summary = None
    v.version_number = 1
    v.intent = None
    v.fermentables = []
    v.hops = []
    v.yeasts = []
    v.adjuncts = []
    v.water_additions = []
    v.mash_steps = []
    v.targets = []
    return v


def _recipe():
    r = MagicMock()
    r.id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    r.brewery_id = "11111111-1111-1111-1111-111111111111"
    r.name = "House IPA"
    r.style = "APA"
    r.description = None
    r.status = "ACTIVE"
    return r


def _calc():
    return {
        "kind_note": "note",
        "recipe_version_id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        "recipe_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "version_number": 1,
        "results": {
            "og": {
                "formula_id": "OG_ESTIMATE",
                "formula_version": "v1",
                "formula_key": "OG_ESTIMATE@v1",
                "status": "OK",
                "value": "1.055",
                "unit": "SG",
                "kind": "ESTIMATED",
                "precision": 3,
                "inputs": {},
                "assumptions": [],
                "missing_inputs": [],
                "invalid_reasons": [],
                "explanation": "x",
                "source_reference": "ADR-003",
            }
        },
    }


@pytest.mark.asyncio
async def test_create_plan_rejects_draft():
    db = AsyncMock()
    with (
        patch("app.services.brew_plan.idempotency_service.lookup_idempotency", new_callable=AsyncMock) as lookup,
        patch("app.services.brew_plan.get_version", new_callable=AsyncMock) as get_version,
    ):
        lookup.return_value = None
        get_version.return_value = _version("DRAFT")
        with pytest.raises(HTTPException) as exc:
            await brew_plan_service.create_brew_plan(
                db,
                "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                BrewPlanCreate(client_submission_id="x1"),
            )
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "RECIPE_VERSION_NOT_PLANABLE"


@pytest.mark.asyncio
async def test_yellow_requires_acknowledgement():
    db = AsyncMock()
    with (
        patch("app.services.brew_plan.idempotency_service.lookup_idempotency", new_callable=AsyncMock) as lookup,
        patch("app.services.brew_plan.get_version", new_callable=AsyncMock) as get_version,
        patch("app.services.brew_plan.get_recipe", new_callable=AsyncMock) as get_recipe,
        patch(
            "app.services.brew_plan.readiness_service.evaluate_recipe_version",
            new_callable=AsyncMock,
        ) as readiness,
    ):
        lookup.return_value = None
        get_version.return_value = _version("ACTIVE")
        get_recipe.return_value = _recipe()
        readiness.return_value = {
            "overall": "YELLOW",
            "summary": "READY WITH WARNINGS",
            "checks": [{"code": "W1", "severity": "WARNING"}],
        }
        with pytest.raises(HTTPException) as exc:
            await brew_plan_service.create_brew_plan(
                db,
                "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                BrewPlanCreate(client_submission_id="y1"),
            )
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "READINESS_ACKNOWLEDGEMENT_REQUIRED"


@pytest.mark.asyncio
async def test_red_requires_acknowledgement():
    db = AsyncMock()
    with (
        patch("app.services.brew_plan.idempotency_service.lookup_idempotency", new_callable=AsyncMock) as lookup,
        patch("app.services.brew_plan.get_version", new_callable=AsyncMock) as get_version,
        patch("app.services.brew_plan.get_recipe", new_callable=AsyncMock) as get_recipe,
        patch(
            "app.services.brew_plan.readiness_service.evaluate_recipe_version",
            new_callable=AsyncMock,
        ) as readiness,
    ):
        lookup.return_value = None
        get_version.return_value = _version("LOCKED")
        get_recipe.return_value = _recipe()
        readiness.return_value = {
            "overall": "RED",
            "summary": "ACTION REQUIRED",
            "checks": [{"code": "B1", "severity": "BLOCKER"}],
        }
        with pytest.raises(HTTPException) as exc:
            await brew_plan_service.create_brew_plan(
                db,
                "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                BrewPlanCreate(client_submission_id="r1"),
            )
        assert exc.value.detail["code"] == "READINESS_ACKNOWLEDGEMENT_REQUIRED"


@pytest.mark.asyncio
async def test_green_succeeds_without_ack_and_preserves_status():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    created_plan = None

    def capture_add(obj):
        nonlocal created_plan
        if isinstance(obj, BrewPlan):
            created_plan = obj
            obj.id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            obj.created_at = datetime.now(timezone.utc)

    db.add.side_effect = capture_add

    with (
        patch("app.services.brew_plan.idempotency_service.lookup_idempotency", new_callable=AsyncMock) as lookup,
        patch(
            "app.services.brew_plan.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ) as record_idemp,
        patch("app.services.brew_plan.get_version", new_callable=AsyncMock) as get_version,
        patch("app.services.brew_plan.get_recipe", new_callable=AsyncMock) as get_recipe,
        patch(
            "app.services.brew_plan.readiness_service.evaluate_recipe_version",
            new_callable=AsyncMock,
        ) as readiness,
        patch(
            "app.services.brew_plan.calculation_service.calculate_version",
            new_callable=AsyncMock,
        ) as calc,
        patch("app.services.brew_plan.audit.record_audit", new_callable=AsyncMock) as audit,
    ):
        lookup.return_value = None
        get_version.return_value = _version("ACTIVE")
        get_recipe.return_value = _recipe()
        readiness.return_value = {
            "overall": "GREEN",
            "summary": "READY TO BREW",
            "checks": [{"code": "OK", "severity": "PASS"}],
        }
        calc.return_value = _calc()
        result = await brew_plan_service.create_brew_plan(
            db,
            "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
            BrewPlanCreate(client_submission_id="g1"),
        )
        assert result["readiness_status"] == "GREEN"
        assert result["readiness_acknowledged"] is False
        assert created_plan is not None
        assert created_plan.readiness_status == "GREEN"
        assert created_plan.planned_calculation_snapshot["results"]["og"]["formula_id"] == "OG_ESTIMATE"
        audit.assert_awaited()
        # Only PLAN_CREATED for GREEN (no READINESS_ACKNOWLEDGED).
        actions = [c.kwargs.get("action") or c.args[1] for c in audit.await_args_list]
        # record_audit is keyword-only for action
        actions = [c.kwargs["action"] for c in audit.await_args_list]
        assert "PLAN_CREATED" in [str(a) for a in actions]
        assert "READINESS_ACKNOWLEDGED" not in [str(a) for a in actions]
        record_idemp.assert_awaited_once()
        db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_yellow_ack_preserves_readiness_status_not_converted():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    created_plan = None

    def capture_add(obj):
        nonlocal created_plan
        if isinstance(obj, BrewPlan):
            created_plan = obj
            obj.id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            obj.created_at = datetime.now(timezone.utc)

    db.add = MagicMock(side_effect=capture_add)

    with (
        patch("app.services.brew_plan.idempotency_service.lookup_idempotency", new_callable=AsyncMock) as lookup,
        patch(
            "app.services.brew_plan.idempotency_service.record_idempotency",
            new_callable=AsyncMock,
        ),
        patch("app.services.brew_plan.get_version", new_callable=AsyncMock) as get_version,
        patch("app.services.brew_plan.get_recipe", new_callable=AsyncMock) as get_recipe,
        patch(
            "app.services.brew_plan.readiness_service.evaluate_recipe_version",
            new_callable=AsyncMock,
        ) as readiness,
        patch(
            "app.services.brew_plan.calculation_service.calculate_version",
            new_callable=AsyncMock,
        ) as calc,
        patch("app.services.brew_plan.audit.record_audit", new_callable=AsyncMock) as audit,
    ):
        lookup.return_value = None
        get_version.return_value = _version("ACTIVE")
        get_recipe.return_value = _recipe()
        readiness.return_value = {
            "overall": "YELLOW",
            "summary": "READY WITH WARNINGS",
            "checks": [{"code": "W1", "severity": "WARNING", "message": "low hops"}],
        }
        calc.return_value = _calc()
        result = await brew_plan_service.create_brew_plan(
            db,
            "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
            BrewPlanCreate(
                client_submission_id="y-ack",
                readiness_acknowledgement=ReadinessAcknowledgement(
                    acknowledged=True, note="proceeding anyway"
                ),
            ),
        )
        assert result["readiness_status"] == "YELLOW"
        assert result["readiness_acknowledged"] is True
        assert created_plan.readiness_status == "YELLOW"
        assert created_plan.readiness_acknowledged is True
        actions = [str(c.kwargs["action"]) for c in audit.await_args_list]
        assert "PLAN_CREATED" in actions
        assert "READINESS_ACKNOWLEDGED" in actions


@pytest.mark.asyncio
async def test_idempotent_replay_returns_original_without_duplicate():
    db = AsyncMock()
    original = {"id": "plan-1", "readiness_status": "GREEN"}
    existing = IdempotencyRecord(
        scope_type="RECIPE_VERSION",
        scope_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        client_submission_id="same",
        operation_type="CREATE_BREW_PLAN",
        request_fingerprint=idempotency_service.fingerprint_payload(
            {"readiness_acknowledgement": None}
        ),
        resource_type="BrewPlan",
        resource_id="plan-1",
        http_status=201,
        response_snapshot=original,
        actor_id="local-brewer",
    )
    with patch(
        "app.services.brew_plan.idempotency_service.lookup_idempotency",
        new_callable=AsyncMock,
    ) as lookup:
        lookup.return_value = existing
        result = await brew_plan_service.create_brew_plan(
            db,
            "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
            BrewPlanCreate(client_submission_id="same"),
        )
        assert result == original
        db.add.assert_not_called()


@pytest.mark.asyncio
async def test_idempotency_conflict_on_different_body():
    db = AsyncMock()
    existing = IdempotencyRecord(
        scope_type="RECIPE_VERSION",
        scope_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        client_submission_id="same",
        operation_type="CREATE_BREW_PLAN",
        request_fingerprint="different-fingerprint",
        resource_type="BrewPlan",
        resource_id="plan-1",
        http_status=201,
        response_snapshot={"id": "plan-1"},
        actor_id="local-brewer",
    )
    with patch(
        "app.services.brew_plan.idempotency_service.lookup_idempotency",
        new_callable=AsyncMock,
    ) as lookup:
        lookup.return_value = existing
        with pytest.raises(HTTPException) as exc:
            await brew_plan_service.create_brew_plan(
                db,
                "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                BrewPlanCreate(client_submission_id="same"),
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "IDEMPOTENCY_CONFLICT"
