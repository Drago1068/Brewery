from decimal import Decimal

from app.domain.enums import ReadinessLevel, ReadinessSeverity
from app.domain.readiness import evaluate_readiness


def _ok_calc(value="1.050"):
    return {
        "status": "OK",
        "kind": "ESTIMATED",
        "value": value,
        "unit": "SG",
        "formula_key": "OG_ESTIMATE@v1",
    }


def test_readiness_green_when_all_pass():
    report = evaluate_readiness(
        batch_size=Decimal("5"),
        batch_size_unit="gal",
        equipment_profile_id="eq-1",
        equipment={
            "name": "BIAB",
            "system_type": "BIAB",
            "kettle_capacity": Decimal("10"),
            "kettle_capacity_unit": "gal",
            "mash_capacity": Decimal("10"),
            "mash_capacity_unit": "gal",
        },
        fermentables=[
            {
                "ingredient_id": "ing-1",
                "ingredient_name": "2-Row",
                "amount": Decimal("10"),
                "unit": "lb",
            }
        ],
        hops=[
            {
                "ingredient_id": "ing-2",
                "ingredient_name": "Citra",
                "amount": Decimal("1"),
                "unit": "oz",
            }
        ],
        yeasts=[
            {
                "ingredient_id": "ing-3",
                "ingredient_name": "US-05",
                "amount": None,
                "unit": None,
            }
        ],
        inventory_by_ingredient_id={
            "ing-1": {"available": Decimal("12"), "unit": "lb", "name": "2-Row"},
            "ing-2": {"available": Decimal("2"), "unit": "oz", "name": "Citra"},
            "ing-3": {"available": Decimal("1"), "unit": "each", "name": "US-05"},
        },
        inventory_by_name={},
        calculation_results={
            "og": _ok_calc("1.056"),
            "fg": _ok_calc("1.014"),
            "abv": {"status": "OK", "kind": "ESTIMATED", "value": "5.51", "unit": "%ABV", "formula_key": "ABV@v1"},
            "ibu": {"status": "OK", "kind": "ESTIMATED", "value": "40", "unit": "IBU", "formula_key": "IBU@v1"},
            "color_srm": {"status": "OK", "kind": "ESTIMATED", "value": "4", "unit": "SRM", "formula_key": "COLOR@v1"},
            "water_total": {"status": "OK", "kind": "CALCULATED", "value": "7", "unit": "gal", "formula_key": "WATER_REQUIREMENTS@v1"},
            "strike_temp": {"status": "OK", "kind": "ESTIMATED", "value": "72", "unit": "C", "formula_key": "STRIKE_TEMP@v1"},
            "pre_boil_volume": {"status": "OK", "kind": "ESTIMATED", "value": "6.5", "unit": "gal", "formula_key": "WATER_REQUIREMENTS@v1"},
        },
    )
    assert report.overall == ReadinessLevel.GREEN
    assert report.summary == "READY TO BREW"
    assert all(c.severity == ReadinessSeverity.PASS for c in report.checks)


def test_inventory_shortage_is_yellow():
    report = evaluate_readiness(
        batch_size=Decimal("5"),
        batch_size_unit="gal",
        equipment_profile_id="eq-1",
        equipment={
            "name": "BIAB",
            "system_type": "BIAB",
            "kettle_capacity": Decimal("10"),
            "kettle_capacity_unit": "gal",
        },
        fermentables=[
            {"ingredient_id": "ing-1", "ingredient_name": "2-Row", "amount": Decimal("10"), "unit": "lb"}
        ],
        hops=[
            {"ingredient_id": "ing-2", "ingredient_name": "Citra", "amount": Decimal("2"), "unit": "oz"}
        ],
        yeasts=[{"ingredient_name": "US-05"}],
        inventory_by_ingredient_id={
            "ing-1": {"available": Decimal("10"), "unit": "lb", "name": "2-Row"},
            "ing-2": {"available": Decimal("1"), "unit": "oz", "name": "Citra"},
        },
        inventory_by_name={"us-05": {"available": Decimal("1"), "unit": "each", "name": "US-05"}},
        calculation_results={
            "og": _ok_calc(),
            "fg": _ok_calc("1.012"),
            "abv": {"status": "OK", "kind": "ESTIMATED", "value": "5.00", "unit": "%ABV"},
            "ibu": {"status": "OK", "kind": "ESTIMATED", "value": "30", "unit": "IBU"},
            "color_srm": {"status": "OK", "kind": "ESTIMATED", "value": "4", "unit": "SRM"},
        },
    )
    assert report.overall == ReadinessLevel.YELLOW
    assert report.summary == "READY WITH WARNINGS"
    assert any("Citra short" in c.message for c in report.checks)


def test_missing_fermentables_and_og_are_red():
    report = evaluate_readiness(
        batch_size=Decimal("5"),
        batch_size_unit="gal",
        equipment_profile_id=None,
        equipment=None,
        fermentables=[],
        hops=[],
        yeasts=[],
        inventory_by_ingredient_id={},
        inventory_by_name={},
        calculation_results={
            "og": {"status": "MISSING", "missing_inputs": ["fermentables"], "formula_key": "OG_ESTIMATE@v1"},
            "fg": {"status": "MISSING", "missing_inputs": ["og"]},
            "abv": {"status": "MISSING", "missing_inputs": ["og", "fg"]},
            "ibu": {"status": "MISSING", "missing_inputs": ["boil_gravity"]},
            "color_srm": {"status": "MISSING", "missing_inputs": ["fermentables"]},
        },
    )
    assert report.overall == ReadinessLevel.RED
    assert report.summary == "ACTION REQUIRED"
    assert any(c.code == "recipe.fermentables" and c.severity == ReadinessSeverity.BLOCKER for c in report.checks)


def test_kettle_too_small_is_blocker():
    report = evaluate_readiness(
        batch_size=Decimal("10"),
        batch_size_unit="gal",
        equipment_profile_id="eq-1",
        equipment={
            "name": "Small kettle",
            "system_type": "BIAB",
            "kettle_capacity": Decimal("5"),
            "kettle_capacity_unit": "gal",
        },
        fermentables=[
            {"ingredient_name": "2-Row", "amount": Decimal("10"), "unit": "lb"}
        ],
        hops=[],
        yeasts=[{"ingredient_name": "US-05"}],
        inventory_by_ingredient_id={},
        inventory_by_name={"2-row": {"available": Decimal("20"), "unit": "lb", "name": "2-Row"}, "us-05": {"available": Decimal("1"), "unit": "each", "name": "US-05"}},
        calculation_results={
            "og": _ok_calc(),
            "fg": _ok_calc("1.012"),
            "abv": {"status": "OK", "value": "5", "unit": "%ABV"},
            "ibu": {"status": "OK", "value": "0", "unit": "IBU"},
            "color_srm": {"status": "OK", "value": "4", "unit": "SRM"},
        },
    )
    assert report.overall == ReadinessLevel.RED
    assert any(c.code == "equipment.kettle" and c.severity == ReadinessSeverity.BLOCKER for c in report.checks)


def test_readiness_does_not_claim_mutation():
    # Structural guarantee documented on API; evaluator itself is pure.
    report = evaluate_readiness(
        batch_size=Decimal("5"),
        batch_size_unit="gal",
        equipment_profile_id="eq",
        equipment={"name": "X", "system_type": "EXTRACT", "kettle_capacity": Decimal("8"), "kettle_capacity_unit": "gal"},
        fermentables=[{"ingredient_name": "DME", "amount": Decimal("6"), "unit": "lb"}],
        hops=[],
        yeasts=[{"ingredient_name": "US-05"}],
        inventory_by_ingredient_id={},
        inventory_by_name={
            "dme": {"available": Decimal("6"), "unit": "lb", "name": "DME"},
            "us-05": {"available": Decimal("1"), "unit": "each", "name": "US-05"},
        },
        calculation_results={
            "og": _ok_calc(),
            "fg": _ok_calc("1.010"),
            "abv": {"status": "OK", "value": "5.25", "unit": "%ABV"},
            "ibu": {"status": "OK", "value": "0", "unit": "IBU"},
            "color_srm": {"status": "OK", "value": "5", "unit": "SRM"},
        },
    )
    assert report.overall in {ReadinessLevel.GREEN, ReadinessLevel.YELLOW}
