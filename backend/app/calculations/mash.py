"""STRIKE_TEMP v1 — infusion mash strike temperature."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.calculations.conversions import convert_mass, convert_volume
from app.calculations.types import (
    CalculationResult,
    CalculationStatus,
    ValueKind,
    invalid_result,
    missing_result,
    round_decimal,
)

FORMULA_ID = "STRIKE_TEMP"
FORMULA_VERSION = "v1"
SOURCE = (
    "ADR-003 §H — Palmer: Tw°F = (0.2/r)(Tmash−Tgrain)+Tmash; r = qt water / lb grain"
)


def strike_temperature(
    *,
    mash_temp_c: Optional[Decimal],
    grain_temp_c: Optional[Decimal],
    mash_water: Optional[Decimal],
    mash_water_unit: Optional[str],
    grain_weight: Optional[Decimal],
    grain_weight_unit: Optional[str],
) -> CalculationResult:
    inputs = {
        "mash_temp_c": str(mash_temp_c) if mash_temp_c is not None else None,
        "grain_temp_c": str(grain_temp_c) if grain_temp_c is not None else None,
        "mash_water": str(mash_water) if mash_water is not None else None,
        "mash_water_unit": mash_water_unit,
        "grain_weight": str(grain_weight) if grain_weight is not None else None,
        "grain_weight_unit": grain_weight_unit,
    }
    missing = [
        name
        for name, val in [
            ("mash_temp_c", mash_temp_c),
            ("grain_temp_c", grain_temp_c),
            ("mash_water", mash_water),
            ("mash_water_unit", mash_water_unit),
            ("grain_weight", grain_weight),
            ("grain_weight_unit", grain_weight_unit),
        ]
        if val is None
    ]
    if missing:
        return missing_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="C",
            missing_inputs=missing,
            precision=1,
            source_reference=SOURCE,
            inputs=inputs,
        )
    assert (
        mash_temp_c is not None
        and grain_temp_c is not None
        and mash_water is not None
        and mash_water_unit is not None
        and grain_weight is not None
        and grain_weight_unit is not None
    )
    try:
        water_qt = convert_volume(mash_water, mash_water_unit, "qt")
        grain_lb = convert_mass(grain_weight, grain_weight_unit, "lb")
    except ValueError as exc:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="C",
            reasons=[str(exc)],
            precision=1,
            source_reference=SOURCE,
            inputs=inputs,
        )
    if grain_lb <= 0 or water_qt <= 0:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="C",
            reasons=["grain_weight and mash_water must be > 0"],
            precision=1,
            source_reference=SOURCE,
            inputs=inputs,
        )

    # Convert temps to F for classic ratio formula, then back to C for output consistency.
    mash_f = mash_temp_c * Decimal("9") / Decimal("5") + Decimal("32")
    grain_f = grain_temp_c * Decimal("9") / Decimal("5") + Decimal("32")
    r = water_qt / grain_lb
    strike_f = (Decimal("0.2") / r) * (mash_f - grain_f) + mash_f
    strike_c = (strike_f - Decimal("32")) * Decimal("5") / Decimal("9")
    strike_r = round_decimal(strike_c, 1)
    return CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.ESTIMATED,
        value=strike_r,
        unit="C",
        precision=1,
        inputs={**inputs, "water_grain_ratio_qt_per_lb": str(round_decimal(r, 3))},
        assumptions=[
            "Classic infusion equation with grain specific heat factor 0.2.",
            "Output reported in °C; internal computation uses °F form of the equation.",
        ],
        explanation=(
            f"ESTIMATED strike temperature {strike_r} °C "
            f"(ratio r={round_decimal(r, 3)} qt/lb; mash={mash_temp_c} °C; grain={grain_temp_c} °C)."
        ),
        source_reference=SOURCE,
    )
