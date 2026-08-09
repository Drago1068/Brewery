"""Deterministic Ready-to-Brew evaluation — side-effect free."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional

from app.domain.enums import ReadinessLevel, ReadinessSeverity


@dataclass(frozen=True)
class ReadinessCheck:
    code: str
    label: str
    severity: ReadinessSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["severity"] = self.severity.value
        return payload


@dataclass(frozen=True)
class ReadinessReport:
    overall: ReadinessLevel
    summary: str
    checks: list[ReadinessCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall.value,
            "summary": self.summary,
            "checks": [c.to_dict() for c in self.checks],
        }


def _overall(checks: list[ReadinessCheck]) -> tuple[ReadinessLevel, str]:
    if any(c.severity == ReadinessSeverity.BLOCKER for c in checks):
        return ReadinessLevel.RED, "ACTION REQUIRED"
    if any(c.severity == ReadinessSeverity.WARNING for c in checks):
        return ReadinessLevel.YELLOW, "READY WITH WARNINGS"
    return ReadinessLevel.GREEN, "READY TO BREW"


def evaluate_readiness(
    *,
    batch_size: Optional[Decimal],
    batch_size_unit: Optional[str],
    equipment_profile_id: Optional[str],
    equipment: Optional[dict[str, Any]],
    fermentables: list[dict[str, Any]],
    hops: list[dict[str, Any]],
    yeasts: list[dict[str, Any]],
    inventory_by_ingredient_id: dict[str, dict[str, Any]],
    inventory_by_name: dict[str, dict[str, Any]],
    calculation_results: dict[str, dict[str, Any]],
) -> ReadinessReport:
    """Evaluate readiness from assembled inputs. Does not mutate anything.

    inventory_* maps values: {available: Decimal, unit: str, name: str}
    calculation_results: output of calculate_recipe()['results']
    """
    checks: list[ReadinessCheck] = []

    # --- Completeness ---
    if batch_size is None or batch_size_unit is None or batch_size <= 0:
        checks.append(
            ReadinessCheck(
                "recipe.batch_size",
                "Batch size",
                ReadinessSeverity.BLOCKER,
                "Batch size is missing or invalid.",
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                "recipe.batch_size",
                "Batch size",
                ReadinessSeverity.PASS,
                f"Batch size {batch_size} {batch_size_unit} present.",
            )
        )

    if not fermentables:
        checks.append(
            ReadinessCheck(
                "recipe.fermentables",
                "Fermentables",
                ReadinessSeverity.BLOCKER,
                "At least one fermentable is required.",
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                "recipe.fermentables",
                "Fermentables",
                ReadinessSeverity.PASS,
                f"{len(fermentables)} fermentable line(s) present.",
            )
        )

    if not yeasts:
        checks.append(
            ReadinessCheck(
                "recipe.yeast",
                "Yeast",
                ReadinessSeverity.BLOCKER,
                "Yeast is required before brew day.",
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                "recipe.yeast",
                "Yeast",
                ReadinessSeverity.PASS,
                "Yeast present.",
            )
        )

    if not equipment_profile_id:
        checks.append(
            ReadinessCheck(
                "recipe.equipment",
                "Equipment",
                ReadinessSeverity.BLOCKER,
                "No equipment profile selected.",
            )
        )
    elif equipment is None:
        checks.append(
            ReadinessCheck(
                "recipe.equipment",
                "Equipment",
                ReadinessSeverity.BLOCKER,
                "Selected equipment profile was not found.",
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                "recipe.equipment",
                "Equipment",
                ReadinessSeverity.PASS,
                f"Equipment profile '{equipment.get('name')}' selected.",
            )
        )

    # --- Equipment compatibility ---
    if equipment is not None and batch_size is not None and batch_size_unit is not None:
        kettle = equipment.get("kettle_capacity")
        kettle_unit = equipment.get("kettle_capacity_unit")
        if kettle is None or kettle_unit is None:
            checks.append(
                ReadinessCheck(
                    "equipment.kettle",
                    "Kettle capacity",
                    ReadinessSeverity.WARNING,
                    "Kettle capacity is not recorded on the equipment profile.",
                )
            )
        elif str(kettle_unit) != str(batch_size_unit):
            checks.append(
                ReadinessCheck(
                    "equipment.kettle",
                    "Kettle capacity",
                    ReadinessSeverity.WARNING,
                    (
                        f"Kettle unit ({kettle_unit}) differs from batch unit ({batch_size_unit}); "
                        "capacity comparison skipped (no silent conversion in readiness v1)."
                    ),
                    {"kettle_capacity": str(kettle), "batch_size": str(batch_size)},
                )
            )
        else:
            kettle_d = Decimal(str(kettle))
            if kettle_d < batch_size:
                checks.append(
                    ReadinessCheck(
                        "equipment.kettle",
                        "Kettle capacity",
                        ReadinessSeverity.BLOCKER,
                        (
                            f"Kettle capacity {kettle_d} {kettle_unit} is below batch size "
                            f"{batch_size} {batch_size_unit}."
                        ),
                        {"kettle_capacity": str(kettle_d), "batch_size": str(batch_size)},
                    )
                )
            else:
                checks.append(
                    ReadinessCheck(
                        "equipment.kettle",
                        "Kettle capacity",
                        ReadinessSeverity.PASS,
                        f"Kettle capacity {kettle_d} {kettle_unit} fits batch size.",
                    )
                )

        mash_cap = equipment.get("mash_capacity")
        mash_unit = equipment.get("mash_capacity_unit")
        system_type = str(equipment.get("system_type") or "")
        if system_type not in {"EXTRACT"} and mash_cap is not None and mash_unit is not None:
            if str(mash_unit) == str(batch_size_unit) and Decimal(str(mash_cap)) < batch_size:
                checks.append(
                    ReadinessCheck(
                        "equipment.mash",
                        "Mash capacity",
                        ReadinessSeverity.WARNING,
                        (
                            f"Mash capacity {mash_cap} {mash_unit} is below batch size "
                            f"{batch_size} {batch_size_unit}."
                        ),
                    )
                )
            else:
                checks.append(
                    ReadinessCheck(
                        "equipment.mash",
                        "Mash capacity",
                        ReadinessSeverity.PASS,
                        "Mash capacity recorded and compatible or not directly comparable.",
                    )
                )

    # --- Inventory ---
    required_lines: list[dict[str, Any]] = []
    for group, lines in (
        ("fermentable", fermentables),
        ("hop", hops),
        ("yeast", yeasts),
    ):
        for line in lines:
            required_lines.append({**line, "_group": group})

    if not required_lines:
        checks.append(
            ReadinessCheck(
                "inventory.none",
                "Inventory",
                ReadinessSeverity.WARNING,
                "No ingredient lines to compare against inventory.",
            )
        )
    else:
        for idx, line in enumerate(required_lines):
            name = str(line.get("ingredient_name") or "Unknown")
            amount = line.get("amount")
            unit = line.get("unit")
            ingredient_id = line.get("ingredient_id")
            code = f"inventory.{line.get('_group')}.{idx}"

            # Yeast amount is optional on recipe lines.
            if line.get("_group") == "yeast" and amount is None:
                inv = None
                if ingredient_id and ingredient_id in inventory_by_ingredient_id:
                    inv = inventory_by_ingredient_id[ingredient_id]
                elif name.lower() in inventory_by_name:
                    inv = inventory_by_name[name.lower()]
                if inv is None or Decimal(str(inv.get("available", 0))) <= 0:
                    checks.append(
                        ReadinessCheck(
                            code,
                            f"{name} availability",
                            ReadinessSeverity.WARNING,
                            f"{name}: no available inventory recorded.",
                            {"ingredient": name},
                        )
                    )
                else:
                    checks.append(
                        ReadinessCheck(
                            code,
                            f"{name} availability",
                            ReadinessSeverity.PASS,
                            f"{name}: inventory present ({inv.get('available')} {inv.get('unit')}).",
                        )
                    )
                continue

            if amount is None or unit is None:
                checks.append(
                    ReadinessCheck(
                        code,
                        f"{name} availability",
                        ReadinessSeverity.WARNING,
                        f"{name}: required amount/unit incomplete; inventory not compared.",
                    )
                )
                continue

            required = Decimal(str(amount))
            inv = None
            if ingredient_id and ingredient_id in inventory_by_ingredient_id:
                inv = inventory_by_ingredient_id[str(ingredient_id)]
            elif name.lower() in inventory_by_name:
                inv = inventory_by_name[name.lower()]

            if inv is None:
                checks.append(
                    ReadinessCheck(
                        code,
                        f"{name} availability",
                        ReadinessSeverity.WARNING,
                        f"{name}: not found in inventory (need {required} {unit}).",
                        {"required": str(required), "unit": unit, "available": "0"},
                    )
                )
                continue

            available = Decimal(str(inv.get("available", 0)))
            inv_unit = str(inv.get("unit") or "")
            if inv_unit and inv_unit != str(unit):
                checks.append(
                    ReadinessCheck(
                        code,
                        f"{name} availability",
                        ReadinessSeverity.WARNING,
                        (
                            f"{name}: inventory unit ({inv_unit}) differs from recipe unit ({unit}); "
                            "shortage not computed (no silent conversion)."
                        ),
                        {
                            "required": str(required),
                            "required_unit": unit,
                            "available": str(available),
                            "available_unit": inv_unit,
                        },
                    )
                )
                continue

            if available < required:
                short = required - available
                checks.append(
                    ReadinessCheck(
                        code,
                        f"{name} availability",
                        ReadinessSeverity.WARNING,
                        f"{name} short by {short} {unit} (need {required}, have {available}).",
                        {
                            "required": str(required),
                            "available": str(available),
                            "shortage": str(short),
                            "unit": unit,
                        },
                    )
                )
            else:
                checks.append(
                    ReadinessCheck(
                        code,
                        f"{name} availability",
                        ReadinessSeverity.PASS,
                        f"{name} available ({available} {unit}).",
                        {"required": str(required), "available": str(available), "unit": unit},
                    )
                )

    # --- Calculations ---
    critical = ("og", "fg", "abv", "ibu", "color_srm")
    for key in critical:
        result = calculation_results.get(key) or {}
        status = result.get("status")
        if status == "OK":
            checks.append(
                ReadinessCheck(
                    f"calc.{key}",
                    f"Calculation {key}",
                    ReadinessSeverity.PASS,
                    f"{key.upper()} complete ({result.get('kind')} {result.get('value')} {result.get('unit') or ''}).".strip(),
                    {"formula_key": result.get("formula_key")},
                )
            )
        elif status == "MISSING":
            severity = (
                ReadinessSeverity.BLOCKER if key in {"og", "fg", "abv"} else ReadinessSeverity.WARNING
            )
            checks.append(
                ReadinessCheck(
                    f"calc.{key}",
                    f"Calculation {key}",
                    severity,
                    f"{key.upper()} cannot be produced — missing inputs: "
                    f"{', '.join(result.get('missing_inputs') or []) or 'unspecified'}.",
                    {"formula_key": result.get("formula_key"), "missing_inputs": result.get("missing_inputs")},
                )
            )
        elif status == "INVALID":
            checks.append(
                ReadinessCheck(
                    f"calc.{key}",
                    f"Calculation {key}",
                    ReadinessSeverity.BLOCKER,
                    f"{key.upper()} invalid: {'; '.join(result.get('invalid_reasons') or []) or 'invalid inputs'}.",
                    {"formula_key": result.get("formula_key")},
                )
            )
        else:
            checks.append(
                ReadinessCheck(
                    f"calc.{key}",
                    f"Calculation {key}",
                    ReadinessSeverity.BLOCKER,
                    f"{key.upper()} was not evaluated.",
                )
            )

    # Soft calculation warnings (water/strike often incomplete without optional fields)
    for key in ("water_total", "strike_temp", "pre_boil_volume"):
        result = calculation_results.get(key) or {}
        status = result.get("status")
        if status == "OK":
            checks.append(
                ReadinessCheck(
                    f"calc.{key}",
                    f"Calculation {key}",
                    ReadinessSeverity.PASS,
                    f"{key} available.",
                    {"formula_key": result.get("formula_key")},
                )
            )
        elif status in {"MISSING", "INVALID"}:
            checks.append(
                ReadinessCheck(
                    f"calc.{key}",
                    f"Calculation {key}",
                    ReadinessSeverity.WARNING,
                    f"{key} incomplete ({status}) — not treated as a hard blocker in v1.",
                    {
                        "missing_inputs": result.get("missing_inputs"),
                        "invalid_reasons": result.get("invalid_reasons"),
                    },
                )
            )

    level, summary = _overall(checks)
    return ReadinessReport(overall=level, summary=summary, checks=checks)
