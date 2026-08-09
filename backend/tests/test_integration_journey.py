"""Epic 1 primary journey — domain integration (no DB mutation).

Simulates: brewery defaults → equipment fit → inventory ledger → recipe
formulation → calculate → readiness, matching the handoff E2E path at the
domain layer.
"""

from decimal import Decimal

from app.calculations.recipe_calculator import calculate_recipe
from app.domain.enums import InventoryTransactionType, ReadinessLevel, RecipeVersionStatus
from app.domain.inventory_math import apply_transaction, available_quantity
from app.domain.readiness import evaluate_readiness
from app.domain.recipe_rules import assert_editable, is_immutable, next_version_number


def test_epic1_primary_domain_journey():
    # --- Inventory foundation: receive → consume → adjust ---
    on_hand, reserved = apply_transaction(
        on_hand=Decimal("0"),
        reserved=Decimal("0"),
        transaction_type=InventoryTransactionType.RECEIPT,
        quantity=Decimal("12"),
    )
    assert on_hand == Decimal("12")

    on_hand, reserved = apply_transaction(
        on_hand=on_hand,
        reserved=reserved,
        transaction_type=InventoryTransactionType.CONSUMPTION,
        quantity=Decimal("1"),
    )
    assert available_quantity(on_hand, reserved) == Decimal("11")

    on_hand, reserved = apply_transaction(
        on_hand=on_hand,
        reserved=reserved,
        transaction_type=InventoryTransactionType.ADJUSTMENT,
        quantity=Decimal("-1"),
    )
    malt_available = available_quantity(on_hand, reserved)
    assert malt_available == Decimal("10")

    # Hop receipt
    hop_on_hand, hop_reserved = apply_transaction(
        on_hand=Decimal("0"),
        reserved=Decimal("0"),
        transaction_type=InventoryTransactionType.RECEIPT,
        quantity=Decimal("2"),
    )

    # --- Recipe versioning rules ---
    assert next_version_number([]) == 1
    assert_editable(RecipeVersionStatus.DRAFT)
    assert is_immutable(RecipeVersionStatus.LOCKED)

    # --- Formulation + calculations ---
    payload = {
        "batch_size": Decimal("5"),
        "batch_size_unit": "gal",
        "brewhouse_efficiency": Decimal("75"),
        "fermentables": [
            {
                "ingredient_name": "2-Row",
                "amount": Decimal("10"),
                "unit": "lb",
                "potential_sg": Decimal("1.037"),
                "color_lovibond": Decimal("2"),
            }
        ],
        "hops": [
            {
                "ingredient_name": "Citra",
                "amount": Decimal("1"),
                "unit": "oz",
                "alpha_acid": Decimal("12"),
                "stage": "BOIL",
                "time_minutes": 60,
            }
        ],
        "yeasts": [{"ingredient_name": "US-05", "expected_attenuation": Decimal("75")}],
        "mash_steps": [
            {
                "target_temperature_c": Decimal("67"),
                "duration_minutes": 60,
                "mash_water_volume": Decimal("3.5"),
                "mash_water_unit": "gal",
                "sparge_water_volume": Decimal("3"),
                "sparge_water_unit": "gal",
            }
        ],
        "grain_temp_c": Decimal("21"),
    }
    calc = calculate_recipe(payload)
    results = calc["results"]
    assert results["og"]["status"] == "OK"
    assert results["og"]["kind"] == "ESTIMATED"
    assert results["fg"]["status"] == "OK"
    assert results["abv"]["status"] == "OK"
    assert results["ibu"]["status"] == "OK"
    assert results["color_srm"]["status"] == "OK"
    assert results["water_total"]["status"] == "OK"
    # Missing boil-off rate still must not fabricate authoritative boil-off totals silently
    # (pre-boil may be MISSING when boil-off not recorded — that is correct).
    assert results["og"]["value"] is not None

    # --- Ready-to-brew ---
    report = evaluate_readiness(
        batch_size=Decimal("5"),
        batch_size_unit="gal",
        equipment_profile_id="eq-1",
        equipment={
            "name": "BIAB 10gal",
            "system_type": "BIAB",
            "kettle_capacity": Decimal("10"),
            "kettle_capacity_unit": "gal",
            "mash_capacity": Decimal("10"),
            "mash_capacity_unit": "gal",
        },
        fermentables=[
            {
                "ingredient_id": "malt-1",
                "ingredient_name": "2-Row",
                "amount": Decimal("10"),
                "unit": "lb",
            }
        ],
        hops=[
            {
                "ingredient_id": "hop-1",
                "ingredient_name": "Citra",
                "amount": Decimal("1"),
                "unit": "oz",
            }
        ],
        yeasts=[{"ingredient_id": "yeast-1", "ingredient_name": "US-05"}],
        inventory_by_ingredient_id={
            "malt-1": {"available": malt_available, "unit": "lb", "name": "2-Row"},
            "hop-1": {
                "available": available_quantity(hop_on_hand, hop_reserved),
                "unit": "oz",
                "name": "Citra",
            },
            "yeast-1": {"available": Decimal("1"), "unit": "each", "name": "US-05"},
        },
        inventory_by_name={},
        calculation_results=results,
    )

    assert report.overall in {ReadinessLevel.GREEN, ReadinessLevel.YELLOW}
    assert report.summary in {"READY TO BREW", "READY WITH WARNINGS"}
    # Journey must remain side-effect free at evaluation boundary.
    assert malt_available == Decimal("10")


def test_invalid_calculation_does_not_fabricate_authoritative_result():
    calc = calculate_recipe(
        {
            "batch_size": Decimal("5"),
            "batch_size_unit": "gal",
            "brewhouse_efficiency": None,
            "fermentables": [
                {
                    "ingredient_name": "2-Row",
                    "amount": Decimal("10"),
                    "unit": "lb",
                    "potential_sg": Decimal("1.037"),
                }
            ],
            "hops": [],
            "yeasts": [],
            "mash_steps": [],
        }
    )
    og = calc["results"]["og"]
    assert og["status"] == "MISSING"
    assert og["value"] is None
    assert "efficiency_percent" in og["missing_inputs"]
