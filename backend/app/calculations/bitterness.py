"""IBU v1 — Tinseth."""

from __future__ import annotations

import math
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

FORMULA_ID = "IBU"
FORMULA_VERSION = "v1"
SOURCE = "ADR-003 — Glenn Tinseth utilization"
PRECISION = 1

# Stages that contribute bitterness in v1.
_BITTERING_STAGES = {"BOIL", "FIRST_WORT", "WHIRLPOOL", "MASH"}
_ZERO_IBU_STAGES = {"DRY_HOP"}


def _tinseth_utilization(boil_gravity: Decimal, time_minutes: Decimal) -> Decimal:
    bg = float(boil_gravity)
    t = float(time_minutes)
    bigness = 1.65 * (0.000125 ** (bg - 1.0))
    boil_factor = (1.0 - math.exp(-0.04 * t)) / 4.15
    return Decimal(str(bigness * boil_factor))


def estimate_ibu(
    *,
    hops: list[dict],
    batch_size: Optional[Decimal],
    batch_size_unit: Optional[str],
    boil_gravity: Optional[Decimal],
) -> CalculationResult:
    """Each hop: amount, unit, alpha_acid (%), stage, time_minutes (required for bittering)."""
    inputs = {
        "hop_count": len(hops),
        "batch_size": str(batch_size) if batch_size is not None else None,
        "batch_size_unit": batch_size_unit,
        "boil_gravity": str(boil_gravity) if boil_gravity is not None else None,
    }
    missing = []
    if batch_size is None:
        missing.append("batch_size")
    if batch_size_unit is None:
        missing.append("batch_size_unit")
    if boil_gravity is None:
        missing.append("boil_gravity")
    if missing:
        return missing_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="IBU",
            missing_inputs=missing,
            precision=PRECISION,
            source_reference=SOURCE,
            inputs=inputs,
        )
    assert batch_size is not None and batch_size_unit is not None and boil_gravity is not None
    if boil_gravity <= 1:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="IBU",
            reasons=["boil_gravity must be > 1.000"],
            precision=PRECISION,
            source_reference=SOURCE,
            inputs=inputs,
        )

    try:
        volume_l = convert_volume(batch_size, batch_size_unit, "L")
    except ValueError as exc:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit="IBU",
            reasons=[str(exc)],
            precision=PRECISION,
            source_reference=SOURCE,
            inputs=inputs,
        )

    total = Decimal("0")
    lines = []
    for idx, hop in enumerate(hops):
        stage = str(hop.get("stage") or "")
        amount = hop.get("amount")
        unit = hop.get("unit")
        alpha = hop.get("alpha_acid")
        time_minutes = hop.get("time_minutes")

        if stage in _ZERO_IBU_STAGES:
            lines.append({"index": idx, "stage": stage, "ibu": "0", "note": "Dry hop contributes 0 IBU in v1"})
            continue
        if stage not in _BITTERING_STAGES:
            return invalid_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="IBU",
                reasons=[f"hops[{idx}].stage '{stage}' is not recognized"],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        if amount is None or unit is None or alpha is None or time_minutes is None:
            return missing_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="IBU",
                missing_inputs=[f"hops[{idx}].amount/unit/alpha_acid/time_minutes"],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        amount_d = Decimal(str(amount))
        alpha_d = Decimal(str(alpha))
        time_d = Decimal(str(time_minutes))
        if amount_d <= 0 or alpha_d <= 0:
            return invalid_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="IBU",
                reasons=[f"hops[{idx}] amount and alpha_acid must be > 0"],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        if time_d < 0:
            return invalid_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="IBU",
                reasons=[f"hops[{idx}].time_minutes must be ≥ 0"],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        # First wort: treat as full boil time already supplied by caller.
        try:
            grams = convert_mass(amount_d, str(unit), "g")
        except ValueError as exc:
            return invalid_result(
                formula_id=FORMULA_ID,
                formula_version=FORMULA_VERSION,
                unit="IBU",
                reasons=[str(exc)],
                precision=PRECISION,
                source_reference=SOURCE,
                inputs=inputs,
            )
        util = _tinseth_utilization(boil_gravity, time_d)
        mg_l = (alpha_d / Decimal("100")) * grams * Decimal("1000") / volume_l
        ibu = util * mg_l
        total += ibu
        lines.append(
            {
                "index": idx,
                "stage": stage,
                "utilization": str(round_decimal(util, 4)),
                "ibu": str(round_decimal(ibu, 2)),
            }
        )

    total_r = round_decimal(total, PRECISION)
    return CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.ESTIMATED,
        value=total_r,
        unit="IBU",
        precision=PRECISION,
        inputs={**inputs, "lines": lines},
        assumptions=[
            "Tinseth utilization with batch volume as post-boil volume proxy when pre-boil gravity unavailable.",
            "Dry hop additions contribute 0 IBU in v1.",
            "No pellet multiplier applied in v1.",
        ],
        explanation=(
            f"ESTIMATED IBU {total_r} via Tinseth: utilization × (α-acid × hop_mass / volume). "
            f"Boil gravity={boil_gravity}, volume={round_decimal(volume_l, 3)} L."
        ),
        source_reference=SOURCE,
    )
