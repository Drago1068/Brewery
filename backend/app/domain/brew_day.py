"""Brew-day snapshot helpers and pure domain rules for E2A-1."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.db.models import EquipmentProfile, Recipe, RecipeVersion
from app.domain.enums import RecipeVersionStatus


PLANABLE_VERSION_STATUSES = frozenset(
    {RecipeVersionStatus.ACTIVE, RecipeVersionStatus.LOCKED}
)


def json_safe(value: Any) -> Any:
    """Convert Decimals and nested structures into JSON-serializable forms."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def assert_planable_version_status(status: str) -> None:
    normalized = status.value if isinstance(status, RecipeVersionStatus) else str(status)
    if normalized == RecipeVersionStatus.DRAFT:
        raise ValueError("BrewPlan requires ACTIVE or LOCKED RecipeVersion; DRAFT is forbidden")
    if normalized not in ("ACTIVE", "LOCKED"):
        raise ValueError(f"BrewPlan requires ACTIVE or LOCKED RecipeVersion; got {normalized}")


def build_equipment_snapshot(equipment: Optional[EquipmentProfile]) -> Optional[dict]:
    if equipment is None:
        return None
    return json_safe(
        {
            "id": equipment.id,
            "name": equipment.name,
            "system_type": equipment.system_type,
            "target_batch_size": equipment.target_batch_size,
            "target_batch_size_unit": equipment.target_batch_size_unit,
            "kettle_capacity": equipment.kettle_capacity,
            "kettle_capacity_unit": equipment.kettle_capacity_unit,
            "mash_capacity": equipment.mash_capacity,
            "mash_capacity_unit": equipment.mash_capacity_unit,
            "boil_off_rate": equipment.boil_off_rate,
            "boil_off_rate_unit": equipment.boil_off_rate_unit,
            "trub_loss": equipment.trub_loss,
            "trub_loss_unit": equipment.trub_loss_unit,
            "fermenter_loss": equipment.fermenter_loss,
            "fermenter_loss_unit": equipment.fermenter_loss_unit,
            "typical_brewhouse_efficiency": equipment.typical_brewhouse_efficiency,
        }
    )


def build_recipe_snapshot(recipe: Recipe, version: RecipeVersion) -> dict:
    """Deep copy of recipe/version/component lines at plan time (immutable baseline)."""
    intent = None
    if version.intent is not None:
        intent = {
            "desired_aroma": version.intent.desired_aroma,
            "desired_flavor": version.intent.desired_flavor,
            "desired_bitterness": version.intent.desired_bitterness,
            "desired_sweetness_dryness": version.intent.desired_sweetness_dryness,
            "desired_body": version.intent.desired_body,
            "desired_carbonation_impression": version.intent.desired_carbonation_impression,
            "overall_objective": version.intent.overall_objective,
        }

    return json_safe(
        {
            "recipe": {
                "id": recipe.id,
                "brewery_id": recipe.brewery_id,
                "name": recipe.name,
                "style": recipe.style,
                "description": recipe.description,
                "status": recipe.status,
            },
            "recipe_version": {
                "id": version.id,
                "recipe_id": version.recipe_id,
                "version_number": version.version_number,
                "status": version.status,
                "batch_size": version.batch_size,
                "batch_size_unit": version.batch_size_unit,
                "equipment_profile_id": version.equipment_profile_id,
                "brewhouse_efficiency": version.brewhouse_efficiency,
                "boil_time_minutes": version.boil_time_minutes,
                "mash_method": version.mash_method,
                "notes": version.notes,
                "change_summary": version.change_summary,
            },
            "intent": intent,
            "fermentables": [
                {
                    "id": f.id,
                    "ingredient_id": f.ingredient_id,
                    "ingredient_name": f.ingredient_name,
                    "manufacturer": f.manufacturer,
                    "amount": f.amount,
                    "unit": f.unit,
                    "color_lovibond": f.color_lovibond,
                    "potential_sg": f.potential_sg,
                    "yield_percent": f.yield_percent,
                    "sort_order": f.sort_order,
                }
                for f in version.fermentables
            ],
            "hops": [
                {
                    "id": h.id,
                    "ingredient_id": h.ingredient_id,
                    "ingredient_name": h.ingredient_name,
                    "manufacturer": h.manufacturer,
                    "amount": h.amount,
                    "unit": h.unit,
                    "alpha_acid": h.alpha_acid,
                    "stage": h.stage,
                    "time_minutes": h.time_minutes,
                    "sort_order": h.sort_order,
                }
                for h in version.hops
            ],
            "yeasts": [
                {
                    "id": y.id,
                    "ingredient_id": y.ingredient_id,
                    "ingredient_name": y.ingredient_name,
                    "manufacturer": y.manufacturer,
                    "amount": y.amount,
                    "unit": y.unit,
                    "expected_attenuation": y.expected_attenuation,
                    "temperature_min_c": y.temperature_min_c,
                    "temperature_max_c": y.temperature_max_c,
                    "sort_order": y.sort_order,
                }
                for y in version.yeasts
            ],
            "adjuncts": [
                {
                    "id": a.id,
                    "ingredient_id": a.ingredient_id,
                    "ingredient_name": a.ingredient_name,
                    "amount": a.amount,
                    "unit": a.unit,
                    "notes": a.notes,
                    "sort_order": a.sort_order,
                }
                for a in version.adjuncts
            ],
            "water_additions": [
                {
                    "id": w.id,
                    "name": w.name,
                    "amount": w.amount,
                    "unit": w.unit,
                    "stage": w.stage,
                    "sort_order": w.sort_order,
                }
                for w in version.water_additions
            ],
            "mash_steps": [
                {
                    "id": m.id,
                    "step_name": m.step_name,
                    "target_temperature_c": m.target_temperature_c,
                    "duration_minutes": m.duration_minutes,
                    "mash_water_volume": m.mash_water_volume,
                    "mash_water_unit": m.mash_water_unit,
                    "sparge_water_volume": m.sparge_water_volume,
                    "sparge_water_unit": m.sparge_water_unit,
                    "sort_order": m.sort_order,
                }
                for m in version.mash_steps
            ],
            "targets": [
                {
                    "id": t.id,
                    "name": t.name,
                    "value": t.value,
                    "unit": t.unit,
                    "notes": t.notes,
                }
                for t in version.targets
            ],
        }
    )


def build_planned_calculation_snapshot(calc_payload: dict) -> dict:
    """Preserve formula identity/version and value kinds from Epic 1 calculation results."""
    results = calc_payload.get("results") or {}
    planned: dict[str, Any] = {}
    for key, result in results.items():
        planned[key] = {
            "formula_id": result.get("formula_id"),
            "formula_version": result.get("formula_version"),
            "formula_key": result.get("formula_key"),
            "status": result.get("status"),
            "value": result.get("value"),
            "unit": result.get("unit"),
            "value_kind": result.get("kind"),
            "precision": result.get("precision"),
            "inputs": result.get("inputs"),
            "assumptions": result.get("assumptions"),
            "missing_inputs": result.get("missing_inputs"),
            "invalid_reasons": result.get("invalid_reasons"),
            "explanation": result.get("explanation"),
            "source_reference": result.get("source_reference"),
        }
    return json_safe(
        {
            "kind_note": calc_payload.get("kind_note"),
            "recipe_version_id": calc_payload.get("recipe_version_id"),
            "recipe_id": calc_payload.get("recipe_id"),
            "version_number": calc_payload.get("version_number"),
            "results": planned,
        }
    )
