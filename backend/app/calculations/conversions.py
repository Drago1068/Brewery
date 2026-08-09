"""Unit conversions — UNIT_CONVERSION v1."""

from __future__ import annotations

from decimal import Decimal

from app.calculations.types import (
    CalculationResult,
    CalculationStatus,
    ValueKind,
    invalid_result,
    missing_result,
    round_decimal,
)

FORMULA_ID = "UNIT_CONVERSION"
FORMULA_VERSION = "v1"
SOURCE = (
    "ADR-003 §J — NIST factors: lb=453.59237 g; oz=28.349523125 g; US gal=3.785411784 L"
)

# Mass to grams
_MASS_TO_G = {
    "g": Decimal("1"),
    "kg": Decimal("1000"),
    "oz": Decimal("28.349523125"),
    "lb": Decimal("453.59237"),
}

# Volume to milliliters
_VOL_TO_ML = {
    "ml": Decimal("1"),
    "L": Decimal("1000"),
    "gal": Decimal("3785.411784"),  # US gallon
    "qt": Decimal("946.352946"),
}


def convert_mass(value: Decimal, from_unit: str, to_unit: str) -> Decimal:
    if from_unit not in _MASS_TO_G or to_unit not in _MASS_TO_G:
        raise ValueError(f"Unsupported mass units: {from_unit} → {to_unit}")
    grams = value * _MASS_TO_G[from_unit]
    return grams / _MASS_TO_G[to_unit]


def convert_volume(value: Decimal, from_unit: str, to_unit: str) -> Decimal:
    if from_unit not in _VOL_TO_ML or to_unit not in _VOL_TO_ML:
        raise ValueError(f"Unsupported volume units: {from_unit} → {to_unit}")
    ml = value * _VOL_TO_ML[from_unit]
    return ml / _VOL_TO_ML[to_unit]


def celsius_to_fahrenheit(c: Decimal) -> Decimal:
    return c * Decimal("9") / Decimal("5") + Decimal("32")


def fahrenheit_to_celsius(f: Decimal) -> Decimal:
    return (f - Decimal("32")) * Decimal("5") / Decimal("9")


def convert(
    *,
    value: Decimal | None,
    from_unit: str | None,
    to_unit: str | None,
    dimension: str,
) -> CalculationResult:
    inputs = {"value": str(value) if value is not None else None, "from_unit": from_unit, "to_unit": to_unit, "dimension": dimension}
    missing = [k for k, v in [("value", value), ("from_unit", from_unit), ("to_unit", to_unit)] if v is None]
    if missing:
        return missing_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit=to_unit,
            missing_inputs=missing,
            precision=6,
            source_reference=SOURCE,
            inputs=inputs,
        )
    assert value is not None and from_unit is not None and to_unit is not None
    try:
        if dimension == "mass":
            out = convert_mass(value, from_unit, to_unit)
        elif dimension == "volume":
            out = convert_volume(value, from_unit, to_unit)
        elif dimension == "temperature":
            if from_unit == "C" and to_unit == "F":
                out = celsius_to_fahrenheit(value)
            elif from_unit == "F" and to_unit == "C":
                out = fahrenheit_to_celsius(value)
            elif from_unit == to_unit:
                out = value
            else:
                return invalid_result(
                    formula_id=FORMULA_ID,
                    formula_version=FORMULA_VERSION,
                    unit=to_unit,
                    reasons=[f"Unsupported temperature conversion {from_unit}→{to_unit}"],
                    precision=4,
                    source_reference=SOURCE,
                    inputs=inputs,
                )
        else:
            return invalid_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit=to_unit,
                reasons=[f"Unknown dimension '{dimension}'"],
                precision=6,
                source_reference=SOURCE,
                inputs=inputs,
            )
    except ValueError as exc:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit=to_unit,
            reasons=[str(exc)],
            precision=6,
            source_reference=SOURCE,
            inputs=inputs,
        )

    rounded = round_decimal(out, 6)
    return CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.CALCULATED,
        value=rounded,
        unit=to_unit,
        precision=6,
        inputs=inputs,
        assumptions=["US gallon = 3.785411784 L when converting gal."],
        explanation=f"Converted {value} {from_unit} → {rounded} {to_unit} ({dimension}).",
        source_reference=SOURCE,
    )
