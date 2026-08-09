"""Golden reference fixtures for ADR-003 calculation formulas."""

from decimal import Decimal

from app.calculations.alcohol import calculate_abv
from app.calculations.attenuation import apparent_attenuation, estimate_fg
from app.calculations.bitterness import estimate_ibu
from app.calculations.color import estimate_srm
from app.calculations.conversions import convert
from app.calculations.gravity import estimate_og
from app.calculations.mash import strike_temperature
from app.calculations.scaling import scale_recipe
from app.calculations.types import CalculationStatus
from app.calculations.water import water_requirements


def test_og_estimate_golden():
    # 10 lb of 1.037 potential at 75% into 5 gal → points = 10*37*0.75=277.5 → OG=1.0555 → 1.056
    result = estimate_og(
        fermentables=[{"amount": Decimal("10"), "unit": "lb", "potential_sg": Decimal("1.037")}],
        batch_size=Decimal("5"),
        batch_size_unit="gal",
        efficiency_percent=Decimal("75"),
    )
    assert result.status == CalculationStatus.OK
    assert result.kind.value == "ESTIMATED"
    assert result.formula_id == "OG_ESTIMATE"
    assert result.value == Decimal("1.056")


def test_og_missing_efficiency():
    result = estimate_og(
        fermentables=[{"amount": Decimal("10"), "unit": "lb", "potential_sg": Decimal("1.037")}],
        batch_size=Decimal("5"),
        batch_size_unit="gal",
        efficiency_percent=None,
    )
    assert result.status == CalculationStatus.MISSING
    assert result.value is None
    assert "efficiency_percent" in result.missing_inputs


def test_fg_and_abv_golden():
    fg = estimate_fg(og=Decimal("1.056"), attenuation_percent=Decimal("75"))
    assert fg.status == CalculationStatus.OK
    assert fg.value == Decimal("1.014")
    abv = calculate_abv(og=Decimal("1.056"), fg=Decimal("1.014"))
    assert abv.status == CalculationStatus.OK
    assert abv.value == Decimal("5.51")
    att = apparent_attenuation(og=Decimal("1.056"), fg=Decimal("1.014"))
    assert att.value == Decimal("75.0")


def test_ibu_tinseth_smoke():
    result = estimate_ibu(
        hops=[
            {
                "amount": Decimal("1"),
                "unit": "oz",
                "alpha_acid": Decimal("12"),
                "stage": "BOIL",
                "time_minutes": 60,
            }
        ],
        batch_size=Decimal("5"),
        batch_size_unit="gal",
        boil_gravity=Decimal("1.056"),
    )
    assert result.status == CalculationStatus.OK
    assert result.value is not None
    assert result.value > 0
    # Dry hop alone → 0
    dry = estimate_ibu(
        hops=[
            {
                "amount": Decimal("2"),
                "unit": "oz",
                "alpha_acid": Decimal("12"),
                "stage": "DRY_HOP",
                "time_minutes": 4320,
            }
        ],
        batch_size=Decimal("5"),
        batch_size_unit="gal",
        boil_gravity=Decimal("1.056"),
    )
    assert dry.value == Decimal("0.0")


def test_color_morey_smoke():
    result = estimate_srm(
        fermentables=[{"amount": Decimal("10"), "unit": "lb", "color_lovibond": Decimal("2")}],
        batch_size=Decimal("5"),
        batch_size_unit="gal",
    )
    assert result.status == CalculationStatus.OK
    assert result.value is not None
    assert result.value > 0


def test_water_no_silent_boil_off_default():
    result = water_requirements(
        mash_water=Decimal("3.5"),
        mash_water_unit="gal",
        sparge_water=Decimal("3"),
        sparge_water_unit="gal",
    )
    assert result.status == CalculationStatus.OK
    assert result.value == Decimal("6.500")
    assert result.inputs["related"]["boil_off"] == "NOT RECORDED"


def test_strike_temp_goldenish():
    # 1.25 qt/lb, mash 152F (66.67C), grain 70F (21.11C)
    result = strike_temperature(
        mash_temp_c=Decimal("66.6667"),
        grain_temp_c=Decimal("21.1111"),
        mash_water=Decimal("12.5"),
        mash_water_unit="qt",
        grain_weight=Decimal("10"),
        grain_weight_unit="lb",
    )
    assert result.status == CalculationStatus.OK
    assert result.value is not None
    # Strike should be a bit above mash temp in C
    assert result.value > Decimal("66")


def test_scaling_doubles_amounts():
    result = scale_recipe(
        from_batch_size=Decimal("5"),
        from_batch_unit="gal",
        to_batch_size=Decimal("10"),
        to_batch_unit="gal",
        amounts=[{"key": "malt", "amount": Decimal("10"), "unit": "lb"}],
    )
    assert result.status == CalculationStatus.OK
    assert result.value == Decimal("2.000000")
    assert result.inputs["scaled"][0]["amount"] == "20.0000"


def test_unit_conversion_lb_to_kg():
    result = convert(value=Decimal("10"), from_unit="lb", to_unit="kg", dimension="mass")
    assert result.status == CalculationStatus.OK
    assert abs(result.value - Decimal("4.535924")) < Decimal("0.0001")


def test_invalid_og_zero_batch():
    result = estimate_og(
        fermentables=[{"amount": Decimal("10"), "unit": "lb", "potential_sg": Decimal("1.037")}],
        batch_size=Decimal("0"),
        batch_size_unit="gal",
        efficiency_percent=Decimal("75"),
    )
    assert result.status == CalculationStatus.INVALID
    assert result.value is None


def test_source_reference_provenance():
    """Runtime source_reference must cite ADR-003 section + equation/constants (not generic labels)."""
    from app.calculations.registry import list_formulas

    expected = {
        "OG_ESTIMATE@v1": "ADR-003 §A —",
        "FG_ESTIMATE@v1": "ADR-003 §B —",
        "APPARENT_ATTENUATION@v1": "ADR-003 §C —",
        "ABV@v1": "ADR-003 §D —",
        "IBU@v1": "ADR-003 §E —",
        "COLOR@v1": "ADR-003 §F —",
        "WATER_REQUIREMENTS@v1": "ADR-003 §G —",
        "STRIKE_TEMP@v1": "ADR-003 §H —",
        "RECIPE_SCALING@v1": "ADR-003 §I —",
        "UNIT_CONVERSION@v1": "ADR-003 §J —",
    }
    banned_fragments = (
        "standard homebrew gravity points method",
        "Palmer / standard infusion equation",
        "NIST / conventional brewing factors",
        "conventional brewing conversion factors",
    )
    by_key = {s["key"]: s for s in list_formulas()}
    for key, prefix in expected.items():
        assert key in by_key, f"missing registry entry {key}"
        ref = by_key[key]["source_reference"]
        assert ref.startswith(prefix), f"{key} source_reference missing section prefix: {ref!r}"
        assert any(ch in ref for ch in ("=", "×", "·", "Σ", "f =", "Tw", "SRM", "U=", "NIST")), (
            f"{key} source_reference lacks equation/constant markers: {ref!r}"
        )
        lower = ref.lower()
        for banned in banned_fragments:
            assert banned not in lower, f"{key} still uses generic provenance: {banned!r}"
