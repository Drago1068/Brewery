"""FG_ESTIMATE and APPARENT_ATTENUATION v1."""

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

FG_ID = "FG_ESTIMATE"
FG_VERSION = "v1"
FG_SOURCE = (
    "ADR-003 §B — FG = 1+(OG−1)×(1−A/100); derived from apparent attenuation"
)
ATT_ID = "APPARENT_ATTENUATION"
ATT_VERSION = "v1"
ATT_SOURCE = (
    "ADR-003 §C — AA% = ((OG−FG)/(OG−1))×100 (SG form; not ASBC Plato)"
)


def estimate_fg(
    *,
    og: Optional[Decimal],
    attenuation_percent: Optional[Decimal],
) -> CalculationResult:
    inputs = {
        "og": str(og) if og is not None else None,
        "attenuation_percent": str(attenuation_percent) if attenuation_percent is not None else None,
    }
    missing = []
    if og is None:
        missing.append("og")
    if attenuation_percent is None:
        missing.append("attenuation_percent")
    if missing:
        return missing_result(
            formula_id=FG_ID,
            formula_version=FG_VERSION,
            unit="SG",
            missing_inputs=missing,
            precision=3,
            source_reference=FG_SOURCE,
            inputs=inputs,
        )
    assert og is not None and attenuation_percent is not None
    if og <= 1:
        return invalid_result(
            formula_id=FG_ID,
            formula_version=FG_VERSION,
            unit="SG",
            reasons=["og must be > 1.000"],
            precision=3,
            source_reference=FG_SOURCE,
            inputs=inputs,
        )
    if attenuation_percent <= 0 or attenuation_percent >= 100:
        return invalid_result(
            formula_id=FG_ID,
            formula_version=FG_VERSION,
            unit="SG",
            reasons=["attenuation_percent must be > 0 and < 100"],
            precision=3,
            source_reference=FG_SOURCE,
            inputs=inputs,
        )
    fg = Decimal("1") + (og - Decimal("1")) * (
        Decimal("1") - attenuation_percent / Decimal("100")
    )
    fg_r = round_decimal(fg, 3)
    return CalculationResult(
        formula_id=FG_ID,
        formula_version=FG_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.ESTIMATED,
        value=fg_r,
        unit="SG",
        precision=3,
        inputs=inputs,
        assumptions=["Uses expected apparent attenuation, not measured fermentation data."],
        explanation=(
            f"ESTIMATED FG {fg_r} from OG {og} at {attenuation_percent}% apparent attenuation: "
            f"FG = 1 + (OG−1)×(1 − att/100)."
        ),
        source_reference=FG_SOURCE,
    )


def apparent_attenuation(
    *,
    og: Optional[Decimal],
    fg: Optional[Decimal],
) -> CalculationResult:
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
            formula_id=ATT_ID,
            formula_version=ATT_VERSION,
            unit="%",
            missing_inputs=missing,
            precision=1,
            source_reference=ATT_SOURCE,
            inputs=inputs,
        )
    assert og is not None and fg is not None
    if og <= 1:
        return invalid_result(
            formula_id=ATT_ID,
            formula_version=ATT_VERSION,
            unit="%",
            reasons=["og must be > 1.000"],
            precision=1,
            source_reference=ATT_SOURCE,
            inputs=inputs,
        )
    if fg >= og:
        return invalid_result(
            formula_id=ATT_ID,
            formula_version=ATT_VERSION,
            unit="%",
            reasons=["fg must be < og"],
            precision=1,
            source_reference=ATT_SOURCE,
            inputs=inputs,
        )
    att = ((og - fg) / (og - Decimal("1"))) * Decimal("100")
    att_r = round_decimal(att, 1)
    return CalculationResult(
        formula_id=ATT_ID,
        formula_version=ATT_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.CALCULATED,
        value=att_r,
        unit="%",
        precision=1,
        inputs=inputs,
        explanation=f"Apparent attenuation {att_r}% = ((OG−FG)/(OG−1))×100.",
        source_reference=ATT_SOURCE,
    )
