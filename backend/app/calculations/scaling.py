"""RECIPE_SCALING v1."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.calculations.conversions import convert_volume
from app.calculations.types import (
    CalculationResult,
    CalculationStatus,
    ValueKind,
    invalid_result,
    missing_result,
    round_decimal,
)

FORMULA_ID = "RECIPE_SCALING"
FORMULA_VERSION = "v1"
SOURCE = "ADR-003 — linear batch-size scaling of ingredient amounts"


def scale_recipe(
    *,
    from_batch_size: Optional[Decimal],
    from_batch_unit: Optional[str],
    to_batch_size: Optional[Decimal],
    to_batch_unit: Optional[str],
    amounts: list[dict[str, Any]],
) -> CalculationResult:
    """amounts: [{key, amount}] — returns scaled amounts in inputs['scaled']."""
    inputs = {
        "from_batch_size": str(from_batch_size) if from_batch_size is not None else None,
        "from_batch_unit": from_batch_unit,
        "to_batch_size": str(to_batch_size) if to_batch_size is not None else None,
        "to_batch_unit": to_batch_unit,
        "amount_count": len(amounts),
    }
    missing = [
        n
        for n, v in [
            ("from_batch_size", from_batch_size),
            ("from_batch_unit", from_batch_unit),
            ("to_batch_size", to_batch_size),
            ("to_batch_unit", to_batch_unit),
        ]
        if v is None
    ]
    if missing:
        return missing_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit=None,
            missing_inputs=missing,
            precision=4,
            source_reference=SOURCE,
            inputs=inputs,
        )
    assert (
        from_batch_size is not None
        and from_batch_unit is not None
        and to_batch_size is not None
        and to_batch_unit is not None
    )
    if from_batch_size <= 0 or to_batch_size <= 0:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit=None,
            reasons=["batch sizes must be > 0"],
            precision=4,
            source_reference=SOURCE,
            inputs=inputs,
        )
    try:
        from_gal = convert_volume(from_batch_size, from_batch_unit, "gal")
        to_gal = convert_volume(to_batch_size, to_batch_unit, "gal")
    except ValueError as exc:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit=None,
            reasons=[str(exc)],
            precision=4,
            source_reference=SOURCE,
            inputs=inputs,
        )
    factor = to_gal / from_gal
    scaled = []
    for item in amounts:
        amt = Decimal(str(item["amount"]))
        scaled.append(
            {
                "key": item.get("key"),
                "amount": str(round_decimal(amt * factor, 4)),
                "unit": item.get("unit"),
            }
        )
    factor_r = round_decimal(factor, 6)
    return CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.CALCULATED,
        value=factor_r,
        unit="scale_factor",
        precision=6,
        inputs={**inputs, "scaled": scaled},
        assumptions=[
            "Linear mass/volume scaling only.",
            "Does not mutate RecipeVersion; caller must create a new version to persist.",
        ],
        explanation=(
            f"Scale factor {factor_r} from {from_batch_size} {from_batch_unit} → "
            f"{to_batch_size} {to_batch_unit}."
        ),
        source_reference=SOURCE,
    )
