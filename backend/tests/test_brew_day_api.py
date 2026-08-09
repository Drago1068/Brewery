"""E2A-1 BrewPlan / BrewSession domain and API tests."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.domain.brew_day import (
    assert_planable_version_status,
    build_planned_calculation_snapshot,
    build_recipe_snapshot,
    json_safe,
)
from app.domain.enums import BREW_DAY_STAGE_SEQUENCE
from app.main import app
from app.schemas.brew_day import BrewPlanCreate, BrewSessionCreate
from app.services import idempotency as idempotency_service

client = TestClient(app)


def test_assert_planable_rejects_draft():
    with pytest.raises(ValueError, match="DRAFT"):
        assert_planable_version_status("DRAFT")


def test_assert_planable_allows_active_and_locked():
    assert_planable_version_status("ACTIVE")
    assert_planable_version_status("LOCKED")


def test_recipe_snapshot_is_value_copy_not_live_reference():
    recipe = MagicMock()
    recipe.id = "r1"
    recipe.brewery_id = "b1"
    recipe.name = "IPA"
    recipe.style = "APA"
    recipe.description = None
    recipe.status = "ACTIVE"

    fermentable = MagicMock()
    fermentable.id = "f1"
    fermentable.ingredient_id = "ing1"
    fermentable.ingredient_name = "2-Row"
    fermentable.manufacturer = None
    fermentable.amount = Decimal("10")
    fermentable.unit = "lb"
    fermentable.color_lovibond = Decimal("2")
    fermentable.potential_sg = Decimal("1.037")
    fermentable.yield_percent = None
    fermentable.sort_order = 0

    version = MagicMock()
    version.id = "v1"
    version.recipe_id = "r1"
    version.version_number = 1
    version.status = "ACTIVE"
    version.batch_size = Decimal("5")
    version.batch_size_unit = "gal"
    version.equipment_profile_id = None
    version.brewhouse_efficiency = Decimal("72")
    version.boil_time_minutes = 60
    version.mash_method = "SINGLE_INFUSION"
    version.notes = None
    version.change_summary = None
    version.intent = None
    version.fermentables = [fermentable]
    version.hops = []
    version.yeasts = []
    version.adjuncts = []
    version.water_additions = []
    version.mash_steps = []
    version.targets = []

    snap = build_recipe_snapshot(recipe, version)
    assert snap["fermentables"][0]["ingredient_name"] == "2-Row"
    assert snap["fermentables"][0]["amount"] == "10"

    # Simulate later ingredient-library / line rename — snapshot must not change.
    fermentable.ingredient_name = "Pale Malt Renamed"
    fermentable.amount = Decimal("99")
    assert snap["fermentables"][0]["ingredient_name"] == "2-Row"
    assert snap["fermentables"][0]["amount"] == "10"


def test_planned_calculation_preserves_formula_identity():
    calc = {
        "kind_note": "note",
        "recipe_version_id": "v1",
        "recipe_id": "r1",
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
    snap = build_planned_calculation_snapshot(calc)
    og = snap["results"]["og"]
    assert og["formula_id"] == "OG_ESTIMATE"
    assert og["formula_version"] == "v1"
    assert og["value_kind"] == "ESTIMATED"
    assert og["value"] == "1.055"


def test_idempotency_fingerprint_stable_and_sensitive():
    a = idempotency_service.fingerprint_payload({"note": "a"})
    b = idempotency_service.fingerprint_payload({"note": "a"})
    c = idempotency_service.fingerprint_payload({"note": "b"})
    assert a == b
    assert a != c


def test_stage_sequence_matches_adr_004():
    assert [s.value for s in BREW_DAY_STAGE_SEQUENCE] == [
        "PRE_BREW",
        "MASH_IN",
        "MASH",
        "MASH_COMPLETE",
        "BOIL",
        "CHILL_KNOCKOUT",
        "TRANSFER",
        "YEAST_PITCH",
        "BREW_DAY_AUDIT",
    ]


def _plan_response(**overrides):
    base = {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "brewery_id": "11111111-1111-1111-1111-111111111111",
        "recipe_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "recipe_version_id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        "status": "CREATED",
        "batch_size": "5",
        "batch_size_unit": "gal",
        "brewhouse_efficiency": "72",
        "equipment_profile_id": None,
        "equipment_snapshot": None,
        "recipe_snapshot": {"fermentables": [{"ingredient_name": "2-Row", "amount": "10"}]},
        "planned_calculation_snapshot": {
            "results": {
                "og": {
                    "formula_id": "OG_ESTIMATE",
                    "formula_version": "v1",
                    "value": "1.055",
                    "value_kind": "ESTIMATED",
                }
            }
        },
        "readiness_status": "GREEN",
        "readiness_summary": "READY TO BREW",
        "readiness_checks_snapshot": [],
        "readiness_acknowledged": False,
        "readiness_acknowledged_at": None,
        "readiness_acknowledged_by": None,
        "readiness_acknowledgement_note": None,
        "created_by": "local-brewer",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


@patch("app.api.v1.brew_day.brew_plan_service.create_brew_plan", new_callable=AsyncMock)
def test_create_brew_plan_api_active(mock_create):
    mock_create.return_value = _plan_response(readiness_status="GREEN")
    response = client.post(
        "/api/v1/recipe-versions/eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee/brew-plans",
        json={"client_submission_id": "sub-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["readiness_status"] == "GREEN"
    assert body["recipe_snapshot"]["fermentables"][0]["ingredient_name"] == "2-Row"
    assert (
        body["planned_calculation_snapshot"]["results"]["og"]["formula_id"] == "OG_ESTIMATE"
    )


@patch("app.api.v1.brew_day.brew_plan_service.create_brew_plan", new_callable=AsyncMock)
def test_create_brew_plan_api_locked(mock_create):
    mock_create.return_value = _plan_response()
    response = client.post(
        "/api/v1/recipe-versions/eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee/brew-plans",
        json={"client_submission_id": "sub-locked"},
    )
    assert response.status_code == 201
    mock_create.assert_awaited_once()


@patch("app.api.v1.brew_day.brew_plan_service.create_brew_plan", new_callable=AsyncMock)
def test_create_brew_plan_yellow_requires_ack_passthrough(mock_create):
    from fastapi import HTTPException

    mock_create.side_effect = HTTPException(
        status_code=422,
        detail={
            "code": "READINESS_ACKNOWLEDGEMENT_REQUIRED",
            "message": "Readiness is YELLOW; explicit acknowledgement is required",
            "readiness_status": "YELLOW",
        },
    )
    response = client.post(
        "/api/v1/recipe-versions/eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee/brew-plans",
        json={"client_submission_id": "sub-y"},
    )
    assert response.status_code == 422


@patch("app.api.v1.brew_day.brew_session_service.create_brew_session", new_callable=AsyncMock)
def test_create_brew_session_api(mock_create):
    stages = [
        {
            "id": f"s{i}",
            "stage_code": code.value,
            "sequence_no": i,
            "status": "PENDING",
            "entered_at": None,
            "exited_at": None,
            "skip_reason": None,
        }
        for i, code in enumerate(BREW_DAY_STAGE_SEQUENCE, start=1)
    ]
    mock_create.return_value = {
        "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "brew_plan_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "brewery_id": "11111111-1111-1111-1111-111111111111",
        "status": "PLANNED",
        "current_stage_code": None,
        "version": 1,
        "started_at": None,
        "closed_at": None,
        "abort_reason": None,
        "created_by": "local-brewer",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage_occurrences": stages,
    }
    response = client.post(
        "/api/v1/brew-plans/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/sessions",
        json={"client_submission_id": "sess-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PLANNED"
    assert body["version"] == 1
    assert body["current_stage_code"] is None
    assert len(body["stage_occurrences"]) == 9
    assert all(s["status"] == "PENDING" for s in body["stage_occurrences"])


@patch(
    "app.api.v1.brew_day.brew_session_service.get_brew_session_read", new_callable=AsyncMock
)
def test_get_brew_session_side_effect_free(mock_get):
    mock_get.return_value = {
        "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "brew_plan_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "brewery_id": "11111111-1111-1111-1111-111111111111",
        "status": "PLANNED",
        "current_stage_code": None,
        "version": 1,
        "started_at": None,
        "closed_at": None,
        "abort_reason": None,
        "created_by": "local-brewer",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage_occurrences": [],
    }
    response = client.get("/api/v1/brew-sessions/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    assert response.status_code == 200
    assert response.json()["version"] == 1
    mock_get.assert_awaited_once()


def test_brew_plan_create_schema_requires_client_submission_id():
    with pytest.raises(Exception):
        BrewPlanCreate(client_submission_id="")


def test_json_safe_decimals():
    assert json_safe({"a": Decimal("1.5")}) == {"a": "1.5"}
