"""COLOR v1 — Morey SRM."""

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

FORMULA_ID = "COLOR"
FORMULA_VERSION = "v1"
SOURCE = (
    "ADR-003 §F — Morey: SRM = 1.4922 × MCU^0.6859; MCU = Σ(W_lb×°L)/V_gal"
)
PRECISION = 1


def estimate_srm(
    *,
    fermentables: list[dict],
    batch_size: Optional[Decimal],
    batch_size_unit: Optional[str],
) -> CalculationResult:
    """Each fermentable: amount, unit, color_lovibond."""
    inputs = {
        "fermentable_count": len(fermentables),
        "batch_size": str(batch_size) if batch_size is not None else None,
        "batch_size_unit": batch_size_unit,
    }
    missing = []
    if batch_size is None:
        missing.append("batch_size")
    if batch_size_unit is None:
        missing.append("batch_size_unit")
    if not fermentables:
        missing.append("fermentables")
    if missing:
        return missing_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="SRM",
            missing_inputs=missing,
            precision=PRECISION,
            source_reference=SOURCE,
            inputs=inputs,
        )
    assert batch_size is not None and batch_size_unit is not None
    try:
        batch_gal = convert_volume(batch_size, batch_size_unit, "gal")
    except ValueError as exc:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="SRM",
            reasons=[str(exc)],
            precision=PRECISION,
            source_reference=SOURCE,
            inputs=inputs,
        )

    mcu = Decimal("0")
    for idx, item in enumerate(fermentables):
        amount = item.get("amount")
        unit = item.get("unit")
        color = item.get("color_lovibond")
        if amount is None or unit is None or color is None:
            return missing_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="SRM",
                missing_inputs=[f"fermentables[{idx}].amount/unit/color_lovibond"],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        amount_d = Decimal(str(amount))
        color_d = Decimal(str(color))
        if amount_d <= 0 or color_d < 0:
            return invalid_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="SRM",
                reasons=[f"fermentables[{idx}] amount must be > 0 and color ≥ 0"],
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
                unit="SRM",
                reasons=[str(exc)],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        mcu += (lbs * color_d) / batch_gal

    # SRM = 1.4922 * MCU^0.6859
    srm = Decimal("1.4922") * (mcu ** Decimal("0.6859"))
    srm_r = round_decimal(srm, PRECISION)
    return CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.ESTIMATED,
        value=srm_r,
        unit="SRM",
        precision=PRECISION,
        inputs={**inputs, "mcu": str(round_decimal(mcu, 3))},
        assumptions=["Morey equation; color inputs are °Lovibond."],
        explanation=(
            f"ESTIMATED color {srm_r} SRM via Morey: MCU={round_decimal(mcu, 3)}, "
            f"SRM = 1.4922 × MCU^0.6859."
        ),
        source_reference=SOURCE,
    )
