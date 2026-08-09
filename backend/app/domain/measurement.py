"""Measurement validation and planned-value helpers (ADR-005)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from app.domain.enums import MeasurementValidationClass, MeasurementValueKind

# Units accepted for E2A-3 capture (conservative).
KNOWN_UNITS = frozenset({"C", "F", "SG", "pH", "L", "gal", "ml", "Brix", "P"})

# Soft unusual thresholds only when definition/requirement bounds absent.
# These are structural sanity checks (not fabricated scientific targets).
STRUCTURAL_SANITY: dict[str, tuple[Decimal, Decimal]] = {
    "SG": (Decimal("0.990"), Decimal("1.200")),
    "pH": (Decimal("0"), Decimal("14")),
    "C": (Decimal("-5"), Decimal("110")),
    "F": (Decimal("20"), Decimal("230")),
}


class ValidationResult:
    def __init__(
        self,
        *,
        ok: bool,
        validation_class: str,
        notes: Optional[str] = None,
        input_error: bool = False,
    ):
        self.ok = ok
        self.validation_class = validation_class
        self.notes = notes
        self.input_error = input_error


def parse_numeric(value: str) -> Optional[Decimal]:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def validate_capture(
    *,
    raw_value: str,
    raw_unit: str,
    measurement_code: str,
    validation_min: Optional[Decimal],
    validation_max: Optional[Decimal],
) -> ValidationResult:
    if raw_value is None or str(raw_value).strip() == "":
        return ValidationResult(
            ok=False,
            validation_class=MeasurementValidationClass.INPUT_ERROR,
            notes="raw_value is required",
            input_error=True,
        )
    if not raw_unit or not str(raw_unit).strip():
        return ValidationResult(
            ok=False,
            validation_class=MeasurementValidationClass.INPUT_ERROR,
            notes="raw_unit is required",
            input_error=True,
        )
    unit = raw_unit.strip()
    if unit not in KNOWN_UNITS:
        return ValidationResult(
            ok=False,
            validation_class=MeasurementValidationClass.INPUT_ERROR,
            notes=f"Unsupported unit '{unit}'",
            input_error=True,
        )
    numeric = parse_numeric(raw_value)
    if numeric is None:
        return ValidationResult(
            ok=False,
            validation_class=MeasurementValidationClass.INPUT_ERROR,
            notes="raw_value must be numeric",
            input_error=True,
        )

    # Explicit requirement/definition bounds → UNUSUAL when outside.
    if validation_min is not None and numeric < validation_min:
        return ValidationResult(
            ok=True,
            validation_class=MeasurementValidationClass.UNUSUAL_VALUE,
            notes=f"{measurement_code} below expected minimum {validation_min}",
        )
    if validation_max is not None and numeric > validation_max:
        return ValidationResult(
            ok=True,
            validation_class=MeasurementValidationClass.UNUSUAL_VALUE,
            notes=f"{measurement_code} above expected maximum {validation_max}",
        )

    # Structural impossibility (e.g. pH 20) → INPUT ERROR.
    sanity = STRUCTURAL_SANITY.get(unit)
    if sanity is not None:
        lo, hi = sanity
        if numeric < lo or numeric > hi:
            # Far outside physical structure → INPUT ERROR; borderline unusual handled above.
            # Use wider "impossible" band: outside sanity is INPUT ERROR when no soft bounds.
            return ValidationResult(
                ok=False,
                validation_class=MeasurementValidationClass.INPUT_ERROR,
                notes=f"{unit} value {numeric} is structurally impossible",
                input_error=True,
            )

    # Domain concern placeholder: extreme-but-possible SG without bounds.
    if unit == "SG" and (numeric < Decimal("1.000") or numeric > Decimal("1.150")):
        return ValidationResult(
            ok=True,
            validation_class=MeasurementValidationClass.DOMAIN_CONCERN,
            notes="SG is unusual for typical wort; observation preserved without diagnosis",
        )

    return ValidationResult(ok=True, validation_class=MeasurementValidationClass.OK)


def planned_from_brew_plan(plan_snapshot: dict[str, Any], code: str) -> tuple[
    Optional[str], Optional[str], Optional[str]
]:
    """Map definition codes to BrewPlan calculation/recipe snapshot values.

    Returns (value, unit, kind) or (None, None, None) when absent.
    Never invents targets.
    """
    calc = (plan_snapshot or {}).get("planned_calculation_snapshot") or {}
    results = calc.get("results") or {}
    recipe = (plan_snapshot or {}).get("recipe_snapshot") or {}
    version = recipe.get("recipe_version") or {}

    mapping = {
        "OG": ("og",),
        "PRE_BOIL_VOLUME": ("pre_boil_volume",),
        "POST_BOIL_VOLUME": ("post_boil_volume",),
        "PRE_BOIL_GRAVITY": (),  # no Epic 1 formula key; leave absent
        "MASH_TEMP": (),
        "MASH_PH": (),
        "KNOCKOUT_TEMP": (),
        "YEAST_PITCH_TEMP": (),
    }
    keys = mapping.get(code, ())
    for key in keys:
        row = results.get(key)
        if not row:
            continue
        value = row.get("value")
        if value is None or value == "":
            continue
        unit = row.get("unit")
        kind = row.get("value_kind") or row.get("kind") or MeasurementValueKind.ESTIMATED
        # Normalize ESTIMATED/CALCULATED from Epic 1; never MEASURED from plan.
        if kind == MeasurementValueKind.MEASURED:
            kind = MeasurementValueKind.ESTIMATED
        return str(value), unit, str(kind)

    # Batch size as planned volume baseline only for volume codes when calc missing.
    if code in {"PRE_BOIL_VOLUME", "POST_BOIL_VOLUME"}:
        batch = version.get("batch_size")
        unit = version.get("batch_size_unit")
        if batch is not None and unit:
            return str(batch), str(unit), MeasurementValueKind.PLANNED

    # Mash step target temperature if present on snapshot.
    if code == "MASH_TEMP":
        steps = recipe.get("mash_steps") or []
        if steps:
            temp = steps[0].get("target_temperature_c")
            if temp is not None:
                return str(temp), "C", MeasurementValueKind.PLANNED

    return None, None, None


def display_value(record) -> tuple[str, str]:
    if record.corrected_value is not None:
        return record.corrected_value, record.corrected_unit or record.raw_unit
    return record.raw_value, record.raw_unit
