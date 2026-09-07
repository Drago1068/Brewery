from decimal import Decimal
from uuid import UUID

from calculations import tinseth_ibu
from sqlalchemy import select
from test_phase2_core import create_foundation, receive_lot

from brewing_api.domain.recipes.models import RecipeIngredient, RecipeProcessStep, RecipeVersion
from brewing_api.platform.database import SessionLocal


def _base_ingredients(equipment, ingredients, malt_lot, hop_lot, extras=None):
    lines = [
        {
            "ingredient_id": ingredients[0]["id"],
            "ingredient_lot_id": malt_lot["id"],
            "amount": "5000",
            "unit": "g",
            "use_stage": "MASH",
        },
        {
            "ingredient_id": ingredients[1]["id"],
            "ingredient_lot_id": hop_lot["id"],
            "amount": "40",
            "unit": "g",
            "use_stage": "BOIL",
            "timing_minutes": 60,
        },
        {
            "ingredient_id": ingredients[2]["id"],
            "amount": "1",
            "unit": "each",
            "use_stage": "FERMENTATION",
        },
    ]
    if extras:
        lines.extend(extras)
    return {
        "name": "Phase 5A-1 Pale",
        "equipment_profile_id": equipment["id"],
        "batch_size_liters": "20",
        "ingredients": lines,
        "process_steps": [
            {
                "step_type": "MASH",
                "sequence": 1,
                "name": "Saccharification",
                "duration_minutes": 60,
                "temperature_c": "66.7",
            },
            {"step_type": "BOIL", "sequence": 2, "name": "Boil", "duration_minutes": 60},
        ],
    }


def test_recipe_addition_edits_persist_on_immutable_version(authenticated_client):
    equipment, location, ingredients = create_foundation(authenticated_client)
    malt_lot = receive_lot(authenticated_client, ingredients[0], location, 10000, "MALT-5A1")
    hop_lot = receive_lot(authenticated_client, ingredients[1], location, 200, "HOP-5A1", "6.2")
    receive_lot(authenticated_client, ingredients[2], location, 2, "YEAST-5A1")
    payload = _base_ingredients(equipment, ingredients, malt_lot, hop_lot)
    payload["ingredients"][0]["amount"] = "4500.2500"
    payload["ingredients"][1]["use_stage"] = "WHIRLPOOL"
    payload["ingredients"][1]["timing_minutes"] = 15
    payload["ingredients"][2]["use_stage"] = "PACKAGING"
    payload["process_steps"] = [
        {
            "step_type": "MASH",
            "sequence": 1,
            "name": "Protein rest",
            "duration_minutes": 20,
            "temperature_c": "52",
        },
        {
            "step_type": "MASH",
            "sequence": 2,
            "name": "Saccharification",
            "duration_minutes": 45,
            "temperature_c": "67",
        },
        {"step_type": "BOIL", "sequence": 3, "name": "Boil", "duration_minutes": 60},
    ]
    created = authenticated_client.post("/api/v1/recipe-designs", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["version_number"] == 1
    by_ingredient = {line["ingredient_id"]: line for line in body["ingredients"]}
    assert Decimal(str(by_ingredient[ingredients[0]["id"]]["amount"])) == Decimal("4500.2500")
    assert by_ingredient[ingredients[0]["id"]]["unit"] == "g"
    assert by_ingredient[ingredients[1]["id"]]["use_stage"] == "WHIRLPOOL"
    assert by_ingredient[ingredients[1]["id"]]["timing_minutes"] == 15
    assert by_ingredient[ingredients[2]["id"]]["use_stage"] == "PACKAGING"
    assert by_ingredient[ingredients[2]["id"]]["timing_minutes"] is None
    assert Decimal(body["calculations"]["ibu_estimate"]) == Decimal("0")
    with SessionLocal() as db:
        version = db.get(RecipeVersion, UUID(body["version_id"]))
        assert version.version_number == 1
        assert version.calculation_inputs["batch_liters"] == "20"
        steps = list(
            db.scalars(
                select(RecipeProcessStep)
                .where(RecipeProcessStep.recipe_version_id == version.id)
                .order_by(RecipeProcessStep.sequence.asc(), RecipeProcessStep.id.asc())
            )
        )
        assert [(step.sequence, step.step_type, step.name) for step in steps] == [
            (1, "MASH", "Protein rest"),
            (2, "MASH", "Saccharification"),
            (3, "BOIL", "Boil"),
        ]
        lines = list(
            db.scalars(
                select(RecipeIngredient).where(RecipeIngredient.recipe_version_id == version.id)
            )
        )
        assert any(line.amount == Decimal("4500.2500") for line in lines)

    clone = authenticated_client.post(
        f"/api/v1/recipe-designs/{body['version_id']}/clone",
        json={"target_batch_liters": "10"},
    )
    assert clone.status_code == 200, clone.text
    assert clone.json()["version_number"] == 2
    reread = authenticated_client.get(f"/api/v1/recipe-designs/{body['version_id']}").json()
    assert reread["version_number"] == 1
    assert reread["calculations"] == body["calculations"]


def test_recipe_addition_validation_rejects_invalid_amount_unit_stage_timing(
    authenticated_client,
):
    equipment, location, ingredients = create_foundation(authenticated_client)
    malt_lot = receive_lot(authenticated_client, ingredients[0], location, 10000, "MALT-BAD")
    hop_lot = receive_lot(authenticated_client, ingredients[1], location, 200, "HOP-BAD", "5.5")
    receive_lot(authenticated_client, ingredients[2], location, 2, "YEAST-BAD")
    payload = _base_ingredients(equipment, ingredients, malt_lot, hop_lot)

    zero = dict(payload)
    zero["ingredients"] = [
        {**payload["ingredients"][0], "amount": "0"},
        *payload["ingredients"][1:],
    ]
    assert authenticated_client.post("/api/v1/recipe-designs", json=zero).status_code == 422

    unit = dict(payload)
    unit["ingredients"] = [{**payload["ingredients"][0], "unit": "L"}, *payload["ingredients"][1:]]
    mismatch = authenticated_client.post("/api/v1/recipe-designs", json=unit)
    assert mismatch.status_code == 400
    assert "canonical unit" in mismatch.json()["detail"]

    unknown_unit = dict(payload)
    unknown_unit["ingredients"] = [
        {**payload["ingredients"][0], "unit": "oz"},
        *payload["ingredients"][1:],
    ]
    assert authenticated_client.post("/api/v1/recipe-designs", json=unknown_unit).status_code == 422

    stage = dict(payload)
    stage["ingredients"] = [
        {**payload["ingredients"][0], "use_stage": "LATER"},
        *payload["ingredients"][1:],
    ]
    assert authenticated_client.post("/api/v1/recipe-designs", json=stage).status_code == 422

    timing = dict(payload)
    timing["ingredients"] = [
        payload["ingredients"][0],
        {**payload["ingredients"][1], "timing_minutes": -1},
        payload["ingredients"][2],
    ]
    assert authenticated_client.post("/api/v1/recipe-designs", json=timing).status_code == 422

    duplicate = dict(payload)
    duplicate["process_steps"] = [
        payload["process_steps"][0],
        {**payload["process_steps"][0], "name": "Copy"},
        payload["process_steps"][1],
    ]
    collision = authenticated_client.post("/api/v1/recipe-designs", json=duplicate)
    assert collision.status_code == 400
    assert "sequences must be unique" in collision.json()["detail"]


def test_valid_canonical_unit_and_boil_timing_feed_calculations(authenticated_client):
    equipment, location, ingredients = create_foundation(authenticated_client)
    malt_lot = receive_lot(authenticated_client, ingredients[0], location, 10000, "MALT-IBU")
    hop_lot = receive_lot(authenticated_client, ingredients[1], location, 200, "HOP-IBU", "6.2")
    receive_lot(authenticated_client, ingredients[2], location, 2, "YEAST-IBU")
    payload = _base_ingredients(equipment, ingredients, malt_lot, hop_lot)
    payload["ingredients"][1]["timing_minutes"] = 15
    created = authenticated_client.post("/api/v1/recipe-designs", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    expected_ibu = tinseth_ibu(
        Decimal("40"),
        Decimal("6.2"),
        Decimal("15"),
        Decimal(body["calculations"]["og"]),
        Decimal("20"),
    )
    assert Decimal(body["calculations"]["ibu_estimate"]) == expected_ibu
    hop_line = next(
        line for line in body["ingredients"] if line["ingredient_id"] == ingredients[1]["id"]
    )
    assert hop_line["unit"] == "g"
    assert hop_line["timing_minutes"] == 15
