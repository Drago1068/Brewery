"""Planned-vs-actual comparison helpers for Brew-Day reporting (E2A-5)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from app.calculations.conversions import convert
from app.calculations.types import CalculationStatus

_VOLUME_UNITS = frozenset({"ml", "L", "gal", "qt"})
_TEMP_UNITS = frozenset({"C", "F"})
_GRAVITY_UNITS = frozenset({"SG", "Brix", "P"})
_PH_UNITS = frozenset({"pH"})


def _parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _dimension_for_units(unit_a: str, unit_b: str) -> Optional[str]:
    if unit_a in _VOLUME_UNITS and unit_b in _VOLUME_UNITS:
        return "volume"
    if unit_a in _TEMP_UNITS and unit_b in _TEMP_UNITS:
        return "temperature"
    if unit_a in _GRAVITY_UNITS and unit_b in _GRAVITY_UNITS:
        return "gravity"
    if unit_a in _PH_UNITS and unit_b in _PH_UNITS:
        return "ph"
    return None


def compare_planned_actual(
    *,
    planned_value: Any,
    planned_unit: Optional[str],
    planned_kind: Optional[str],
    actual_value: Any,
    actual_unit: Optional[str],
    actual_kind: Optional[str],
    requirement_status: str,
) -> dict[str, Any]:
    """Return comparison block. Never invent a delta when actual is missing."""
    base = {
        "planned_value": planned_value,
        "planned_unit": planned_unit,
        "planned_kind": planned_kind,
        "actual_value": actual_value,
        "actual_unit": actual_unit,
        "actual_kind": actual_kind,
        "requirement_status": requirement_status,
        "comparison_available": False,
        "delta": None,
        "percent_delta": None,
        "comparison_unit": None,
        "unavailable_reason": None,
    }

    if requirement_status != "CAPTURED" or actual_value is None:
        base["unavailable_reason"] = "ACTUAL_MISSING"
        return base
    if planned_value is None or planned_unit is None:
        base["unavailable_reason"] = "PLANNED_MISSING"
        return base
    if actual_unit is None:
        base["unavailable_reason"] = "ACTUAL_UNIT_MISSING"
        return base

    planned_num = _parse_decimal(planned_value)
    actual_num = _parse_decimal(actual_value)
    if planned_num is None or actual_num is None:
        base["unavailable_reason"] = "NON_NUMERIC"
        return base

    if planned_unit == actual_unit:
        delta = actual_num - planned_num
        percent = None
        if planned_num != 0:
            percent = str((delta / planned_num) * Decimal("100"))
        base.update(
            {
                "comparison_available": True,
                "delta": str(delta),
                "percent_delta": percent,
                "comparison_unit": planned_unit,
                "unavailable_reason": None,
            }
        )
        return base

    dimension = _dimension_for_units(planned_unit, actual_unit)
    if dimension is None:
        base["unavailable_reason"] = "INCOMPATIBLE_UNITS"
        return base

    # Gravity/pH: only identical units (no silent Brix↔SG without provenance).
    if dimension in ("gravity", "ph"):
        base["unavailable_reason"] = "INCOMPATIBLE_UNITS"
        return base

    converted = convert(
        value=actual_num,
        from_unit=actual_unit,
        to_unit=planned_unit,
        dimension=dimension,
    )
    if converted.status != CalculationStatus.OK or converted.value is None:
        base["unavailable_reason"] = "UNIT_CONVERSION_UNAVAILABLE"
        return base

    actual_in_planned = Decimal(str(converted.value))
    delta = actual_in_planned - planned_num
    percent = None
    if planned_num != 0:
        percent = str((delta / planned_num) * Decimal("100"))
    base.update(
        {
            "comparison_available": True,
            "delta": str(delta),
            "percent_delta": percent,
            "comparison_unit": planned_unit,
            "actual_value_normalized": str(actual_in_planned),
            "conversion_formula_id": converted.formula_id,
            "conversion_formula_version": converted.formula_version,
            "unavailable_reason": None,
        }
    )
    return base
