from decimal import Decimal

import pytest
from calculations import (
    abv,
    apparent_attenuation,
    brewing_water_volumes,
    expected_fg,
    expected_og,
    fermentable_gravity_points,
    mineral_ppm,
    morey_srm,
    priming_sugar_grams,
    recipe_scaling_factors,
    strike_temperature_c,
    tinseth_ibu,
    yeast_pitch_cells,
)
from calculations.units import (
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    gallons_to_liters,
    grams_to_ounces,
    kilograms_to_pounds,
    liters_to_gallons,
    ounces_to_grams,
    pounds_to_kilograms,
)


def test_unit_conversion_golden_round_trips_without_intermediate_rounding():
    assert gallons_to_liters(Decimal("1")) == Decimal("3.785411784")
    assert liters_to_gallons(gallons_to_liters(Decimal("5"))) == Decimal("5")
    assert pounds_to_kilograms(Decimal("1")) == Decimal("0.45359237")
    assert kilograms_to_pounds(pounds_to_kilograms(Decimal("12.5"))) == Decimal("12.5")
    assert ounces_to_grams(Decimal("1")) == Decimal("28.349523125")
    assert grams_to_ounces(ounces_to_grams(Decimal("4"))) == Decimal("4")
    assert fahrenheit_to_celsius(Decimal("212")) == Decimal("100")
    assert celsius_to_fahrenheit(Decimal("0")) == Decimal("32")


def test_extract_fg_attenuation_and_abv_golden_case():
    contribution = fermentable_gravity_points(
        Decimal("37"), Decimal("4535.9237"), Decimal("18.92705892"), Decimal("0.75")
    )
    assert contribution == pytest.approx(Decimal("55.5"), abs=Decimal("0.0001"))
    og = expected_og([contribution])
    fg = expected_fg(og, Decimal("0.75"))
    assert og == pytest.approx(Decimal("1.0555"), abs=Decimal("0.00001"))
    assert fg == pytest.approx(Decimal("1.013875"), abs=Decimal("0.00001"))
    assert apparent_attenuation(og, fg) == pytest.approx(Decimal("0.75"))
    assert abv(og, fg) == pytest.approx(Decimal("5.46328125"), abs=Decimal("0.00001"))


def test_tinseth_and_morey_recognized_model_golden_cases():
    ibu = tinseth_ibu(
        Decimal("28.3495"), Decimal("5"), Decimal("60"), Decimal("1.050"), Decimal("18.9271")
    )
    assert ibu == pytest.approx(Decimal("17.3"), abs=Decimal("0.2"))
    color = morey_srm([(Decimal("4535.9237"), Decimal("2"))], Decimal("18.92705892"))
    assert color == pytest.approx(Decimal("3.86"), abs=Decimal("0.02"))


def test_water_strike_pitch_carbonation_and_mineral_foundations():
    water = brewing_water_volumes(
        Decimal("5"),
        Decimal("20"),
        Decimal("3"),
        Decimal("60"),
        Decimal("3.5"),
        Decimal("0.8"),
        Decimal("0.5"),
        Decimal("1"),
        Decimal("1"),
        Decimal("0.5"),
    )
    assert water.strike_liters == Decimal("15.5")
    assert water.post_boil_liters == Decimal("21.5")
    assert water.pre_boil_liters == Decimal("26.0")
    assert water.total_liquor_liters == Decimal("30.5")
    strike = strike_temperature_c(Decimal("67"), Decimal("20"), Decimal("3"))
    cells = yeast_pitch_cells(Decimal("20"), Decimal("1.050"), Decimal("0.75"))
    sugar = priming_sugar_grams(Decimal("19"), Decimal("2.4"), Decimal("20"))
    assert strike == pytest.approx(Decimal("73.54"), abs=Decimal("0.02"))
    assert cells == pytest.approx(Decimal("184000000000"), rel=Decimal("0.02"))
    assert sugar == pytest.approx(Decimal("117"), abs=Decimal("3"))
    assert mineral_ppm(Decimal("1"), Decimal("0.233"), Decimal("10")) == Decimal("23.3")


def test_process_aware_scaling_distinguishes_efficiency_and_liquor():
    factors = recipe_scaling_factors(
        Decimal("20"), Decimal("40"), Decimal("0.75"), Decimal("0.70"), Decimal("30"), Decimal("63")
    )
    assert factors.volume == Decimal("2")
    assert factors.fermentable == pytest.approx(Decimal("2.142857"), abs=Decimal("0.000001"))
    assert factors.hop == Decimal("2")
    assert factors.yeast == Decimal("2")
    assert factors.salt == Decimal("2.1")
