"""WATER_REQUIREMENTS and volume helpers v1."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.calculations.conversions import convert_volume
from app.calculations.types import (
    CalculationResult,
    CalculationStatus,
    ValueKind,
    invalid_result,
    missing_result,
    round_decimal,
)

FORMULA_ID = "WATER_REQUIREMENTS"
FORMULA_VERSION = "v1"
SOURCE = (
    "ADR-003 §G — V_total = V_mash + V_sparge(optional); losses NOT RECORDED if absent"
)


def water_requirements(
    *,
    mash_water: Optional[Decimal],
    mash_water_unit: Optional[str],
    sparge_water: Optional[Decimal] = None,
    sparge_water_unit: Optional[str] = None,
    boil_off: Optional[Decimal] = None,
    boil_off_unit: Optional[str] = None,
    trub_loss: Optional[Decimal] = None,
    trub_loss_unit: Optional[str] = None,
    output_unit: str = "gal",
) -> CalculationResult:
    """Total brewing water = mash + sparge (when provided).

    Boil-off and trub are reported as related volume figures when present, but are NOT
    invented when absent.
    """
    inputs = {
        "mash_water": str(mash_water) if mash_water is not None else None,
        "mash_water_unit": mash_water_unit,
        "sparge_water": str(sparge_water) if sparge_water is not None else None,
        "sparge_water_unit": sparge_water_unit,
        "boil_off": str(boil_off) if boil_off is not None else None,
        "trub_loss": str(trub_loss) if trub_loss is not None else None,
        "output_unit": output_unit,
    }
    if mash_water is None or mash_water_unit is None:
        return missing_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit=output_unit,
            missing_inputs=["mash_water", "mash_water_unit"]
            if mash_water is None and mash_water_unit is None
            else (["mash_water"] if mash_water is None else ["mash_water_unit"]),
            precision=3,
            source_reference=SOURCE,
            inputs=inputs,
        )
    assert mash_water is not None and mash_water_unit is not None
    if mash_water <= 0:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit=output_unit,
            reasons=["mash_water must be > 0"],
            precision=3,
            source_reference=SOURCE,
            inputs=inputs,
        )
    if (sparge_water is None) ^ (sparge_water_unit is None):
        return missing_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit=output_unit,
            missing_inputs=["sparge_water/sparge_water_unit pair incomplete"],
            precision=3,
            source_reference=SOURCE,
            inputs=inputs,
        )

    try:
        total = convert_volume(mash_water, mash_water_unit, output_unit)
        if sparge_water is not None and sparge_water_unit is not None:
            if sparge_water < 0:
                return invalid_result(
                    formula_id=FORMULA_ID,
                    formula_version=FORMULA_VERSION,
                    unit=output_unit,
                    reasons=["sparge_water must be ≥ 0"],
                    precision=3,
                    source_reference=SOURCE,
                    inputs=inputs,
                )
            total += convert_volume(sparge_water, sparge_water_unit, output_unit)
    except ValueError as exc:
        return invalid_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit=output_unit,
            reasons=[str(exc)],
            precision=3,
            source_reference=SOURCE,
            inputs=inputs,
        )

    related: dict[str, str] = {}
    assumptions = [
        (
            "V_total means mash plus sparge water recorded for the recipe; "
            "it is not a full loss-adjusted liquor requirement unless those "
            "additional values are separately available."
        ),
        "Missing boil-off/trub values are reported as NOT RECORDED — not defaulted.",
    ]
    if boil_off is not None and boil_off_unit is not None:
        related["boil_off"] = str(
            round_decimal(convert_volume(boil_off, boil_off_unit, output_unit), 3)
        )
    else:
        related["boil_off"] = "NOT RECORDED"
    if trub_loss is not None and trub_loss_unit is not None:
        related["trub_loss"] = str(
            round_decimal(convert_volume(trub_loss, trub_loss_unit, output_unit), 3)
        )
    else:
        related["trub_loss"] = "NOT RECORDED"

    total_r = round_decimal(total, 3)
    return CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.CALCULATED,
        value=total_r,
        unit=output_unit,
        precision=3,
        inputs={**inputs, "related": related},
        assumptions=assumptions,
        explanation=(
            f"Recorded mash+sparge water {total_r} {output_unit} = mash"
            + (" + sparge" if sparge_water is not None else "")
            + f". Boil-off: {related['boil_off']}; trub loss: {related['trub_loss']}."
        ),
        source_reference=SOURCE,
    )


def pre_post_boil_volumes(
    *,
    batch_size: Optional[Decimal],
    batch_size_unit: Optional[str],
    boil_off: Optional[Decimal],
    boil_off_unit: Optional[str],
    trub_loss: Optional[Decimal] = None,
    trub_loss_unit: Optional[str] = None,
) -> dict[str, CalculationResult]:
    """Derive pre-boil / post-boil when loss inputs exist; otherwise MISSING."""
    out_unit = batch_size_unit or "gal"
    if batch_size is None or batch_size_unit is None:
        missing = missing_result(
            formula_id="WATER_REQUIREMENTS",
            formula_version=FORMULA_VERSION,
            unit=out_unit,
            missing_inputs=["batch_size", "batch_size_unit"],
            precision=3,
            source_reference=SOURCE,
        )
        return {"pre_boil_volume": missing, "post_boil_volume": missing, "boil_off": missing}

    # Post-boil ≈ batch + trub (if known); else post-boil treated as batch (assumption noted)
    post = batch_size
    assumptions = []
    if trub_loss is not None and trub_loss_unit is not None:
        post = batch_size + convert_volume(trub_loss, trub_loss_unit, batch_size_unit)
        assumptions.append("Post-boil volume = batch size + trub loss.")
    else:
        assumptions.append("Post-boil volume approximated as batch size (trub loss NOT RECORDED).")

    post_result = CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.ESTIMATED,
        value=round_decimal(post, 3),
        unit=batch_size_unit,
        precision=3,
        inputs={
            "batch_size": str(batch_size),
            "trub_loss": str(trub_loss) if trub_loss is not None else "NOT RECORDED",
        },
        assumptions=assumptions,
        explanation=f"ESTIMATED post-boil volume {round_decimal(post, 3)} {batch_size_unit}.",
        source_reference=SOURCE,
    )

    if boil_off is None or boil_off_unit is None:
        boil_missing = missing_result(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            unit=batch_size_unit,
            missing_inputs=["boil_off", "boil_off_unit"],
            precision=3,
            source_reference=SOURCE,
        )
        return {
            "pre_boil_volume": boil_missing,
            "post_boil_volume": post_result,
            "boil_off": boil_missing,
        }

    boil_off_converted = convert_volume(boil_off, boil_off_unit, batch_size_unit)
    pre = post + boil_off_converted
    boil_result = CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.CALCULATED,
        value=round_decimal(boil_off_converted, 3),
        unit=batch_size_unit,
        precision=3,
        inputs={"boil_off": str(boil_off), "boil_off_unit": boil_off_unit},
        explanation=f"Boil-off {round_decimal(boil_off_converted, 3)} {batch_size_unit}.",
        source_reference=SOURCE,
    )
    pre_result = CalculationResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        status=CalculationStatus.OK,
        kind=ValueKind.ESTIMATED,
        value=round_decimal(pre, 3),
        unit=batch_size_unit,
        precision=3,
        inputs={"post_boil": str(post), "boil_off": str(boil_off_converted)},
        assumptions=["Pre-boil = post-boil + boil-off."],
        explanation=f"ESTIMATED pre-boil volume {round_decimal(pre, 3)} {batch_size_unit}.",
        source_reference=SOURCE,
    )
    return {
        "pre_boil_volume": pre_result,
        "post_boil_volume": post_result,
        "boil_off": boil_result,
    }
