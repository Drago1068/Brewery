"""OG_ESTIMATE v1 — gravity points method."""

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

FORMULA_ID = "OG_ESTIMATE"
FORMULA_VERSION = "v1"
SOURCE = (
    "ADR-003 §A — OG = 1 + Σ(W_lb×(P−1)×1000×E/100) / (V_gal×1000); Palmer/Daniels PPG"
)
PRECISION = 3


def estimate_og(
    *,
    fermentables: list[dict],
    batch_size: Optional[Decimal],
    batch_size_unit: Optional[str],
    efficiency_percent: Optional[Decimal],
) -> CalculationResult:
    """Estimate original gravity.

    Each fermentable dict: amount, unit, potential_sg (e.g. 1.037).
    potential points = (potential_sg - 1) * 1000
    """
    inputs = {
        "fermentable_count": len(fermentables),
        "batch_size": str(batch_size) if batch_size is not None else None,
        "batch_size_unit": batch_size_unit,
        "efficiency_percent": str(efficiency_percent) if efficiency_percent is not None else None,
    }
    missing: list[str] = []
    if batch_size is None:
        missing.append("batch_size")
    if batch_size_unit is None:
        missing.append("batch_size_unit")
    if efficiency_percent is None:
        missing.append("efficiency_percent")
    if not fermentables:
        missing.append("fermentables")
    if missing:
        return missing_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="SG",
            missing_inputs=missing,
            precision=PRECISION,
            source_reference=SOURCE,
            inputs=inputs,
        )

    assert batch_size is not None and batch_size_unit is not None and efficiency_percent is not None
    if batch_size <= 0:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="SG",
            reasons=["batch_size must be > 0"],
            precision=PRECISION,
            source_reference=SOURCE,
            inputs=inputs,
        )
    if efficiency_percent <= 0 or efficiency_percent > 100:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="SG",
            reasons=["efficiency_percent must be > 0 and ≤ 100"],
            precision=PRECISION,
            source_reference=SOURCE,
            inputs=inputs,
        )

    try:
        batch_gal = convert_volume(batch_size, batch_size_unit, "gal")
    except ValueError as exc:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="SG",
            reasons=[str(exc)],
            precision=PRECISION,
            source_reference=SOURCE,
            inputs=inputs,
        )

    total_points = Decimal("0")
    line_details = []
    for idx, item in enumerate(fermentables):
        amount = item.get("amount")
        unit = item.get("unit")
        potential = item.get("potential_sg")
        if amount is None or unit is None or potential is None:
            return missing_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="SG",
                missing_inputs=[f"fermentables[{idx}].amount/unit/potential_sg"],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        amount_d = Decimal(str(amount))
        potential_d = Decimal(str(potential))
        if amount_d <= 0:
            return invalid_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="SG",
                reasons=[f"fermentables[{idx}].amount must be > 0"],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        if potential_d <= 1:
            return invalid_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="SG",
                reasons=[f"fermentables[{idx}].potential_sg must be > 1.000"],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        try:
            lbs = convert_mass(amount_d, str(unit), "lb")
        except ValueError as exc:
            return invalid_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="SG",
                reasons=[str(exc)],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        points = (potential_d - Decimal("1")) * Decimal("1000")
        contribution = lbs * points * (efficiency_percent / Decimal("100"))
        total_points += contribution
        line_details.append(
            {
                "index": idx,
                "lbs": str(round_decimal(lbs, 4)),
                "points": str(round_decimal(points, 2)),
                "contribution": str(round_decimal(contribution, 2)),
            }
        )

    og = Decimal("1") + (total_points / batch_gal) / Decimal("1000")
    og_r = round_decimal(og, PRECISION)
    return CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.ESTIMATED,
        value=og_r,
        unit="SG",
        precision=PRECISION,
        inputs={**inputs, "lines": line_details, "total_points": str(round_decimal(total_points, 2))},
        assumptions=[
            "Potential is as-is laboratory/extract potential (SG for 1 lb in 1 gal at 100% efficiency).",
            "Efficiency is overall brewhouse efficiency into the batch volume.",
        ],
        explanation=(
            f"ESTIMATED OG {og_r}: sum(weight_lb × potential_points × efficiency) / batch_gal, "
            f"then SG = 1 + points/1000. Total points={round_decimal(total_points, 2)}, "
            f"batch={round_decimal(batch_gal, 3)} gal, efficiency={efficiency_percent}%."
        ),
        source_reference=SOURCE,
    )
