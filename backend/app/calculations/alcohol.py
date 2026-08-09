"""ABV v1."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.calculations.types import (
    CalculationResult,
    CalculationStatus,
    ValueKind,
    invalid_result,
    missing_result,
    round_decimal,
)

FORMULA_ID = "ABV"
FORMULA_VERSION = "v1"
SOURCE = "ADR-003 — ABV% = (OG − FG) × 131.25"


def calculate_abv(*, og: Optional[Decimal], fg: Optional[Decimal]) -> CalculationResult:
    inputs = {
        "og": str(og) if og is not None else None,
        "fg": str(fg) if fg is not None else None,
    }
    missing = []
    if og is None:
        missing.append("og")
    if fg is None:
        missing.append("fg")
    if missing:
        return missing_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="%ABV",
            missing_inputs=missing,
            precision=2,
            source_reference=SOURCE,
            inputs=inputs,
        )
    assert og is not None and fg is not None
    if og <= fg:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="%ABV",
            reasons=["og must be greater than fg"],
            precision=2,
            source_reference=SOURCE,
            inputs=inputs,
        )
    abv = (og - fg) * Decimal("131.25")
    abv_r = round_decimal(abv, 2)
    return CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.ESTIMATED,
        value=abv_r,
        unit="%ABV",
        precision=2,
        inputs=inputs,
        assumptions=["Simple linear ABV model; not Balling/alternate high-gravity corrections."],
        explanation=f"ESTIMATED ABV {abv_r}% = (OG − FG) × 131.25 using OG={og}, FG={fg}.",
        source_reference=SOURCE,
    )
