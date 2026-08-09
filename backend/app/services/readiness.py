from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EquipmentProfile
from app.domain.readiness import evaluate_readiness
from app.services.calculation import calculate_version
from app.services.inventory import list_availability
from app.services.recipe import get_recipe, get_version


async def evaluate_recipe_version(db: AsyncSession, version_id: str) -> dict:
    """Side-effect free readiness evaluation for a RecipeVersion."""
    version = await get_version(db, version_id)
    recipe = await get_recipe(db, version.recipe_id)

    equipment = None
    if version.equipment_profile_id:
        eq = await db.get(EquipmentProfile, version.equipment_profile_id)
        if eq is not None:
            equipment = {
                "id": eq.id,
                "name": eq.name,
                "system_type": eq.system_type,
                "kettle_capacity": eq.kettle_capacity,
                "kettle_capacity_unit": eq.kettle_capacity_unit,
                "mash_capacity": eq.mash_capacity,
                "mash_capacity_unit": eq.mash_capacity_unit,
            }

    calc_payload = await calculate_version(db, version_id)
    calc_results = calc_payload.get("results") or {}

    availability = await list_availability(db, recipe.brewery_id)
    by_id: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for row in availability:
        entry = {
            "available": row.quantity_available,
            "unit": row.unit.value if hasattr(row.unit, "value") else row.unit,
            "name": row.name,
        }
        by_id[row.ingredient_id] = entry
        by_name[row.name.lower()] = entry

    fermentables = [
        {
            "ingredient_id": f.ingredient_id,
            "ingredient_name": f.ingredient_name,
            "amount": f.amount,
            "unit": f.unit,
        }
        for f in version.fermentables
    ]
    hops = [
        {
            "ingredient_id": h.ingredient_id,
            "ingredient_name": h.ingredient_name,
            "amount": h.amount,
            "unit": h.unit,
        }
        for h in version.hops
    ]
    yeasts = [
        {
            "ingredient_id": y.ingredient_id,
            "ingredient_name": y.ingredient_name,
            "amount": y.amount,
            "unit": y.unit,
        }
        for y in version.yeasts
    ]

    report = evaluate_readiness(
        batch_size=version.batch_size,
        batch_size_unit=version.batch_size_unit,
        equipment_profile_id=version.equipment_profile_id,
        equipment=equipment,
        fermentables=fermentables,
        hops=hops,
        yeasts=yeasts,
        inventory_by_ingredient_id=by_id,
        inventory_by_name=by_name,
        calculation_results=calc_results,
    )

    return {
        "recipe_id": recipe.id,
        "recipe_name": recipe.name,
        "recipe_version_id": version.id,
        "version_number": version.version_number,
        "mutates_inventory": False,
        "mutates_recipe": False,
        **report.to_dict(),
        "calculation_snapshot": {
            key: {
                "status": val.get("status"),
                "value": val.get("value"),
                "unit": val.get("unit"),
                "kind": val.get("kind"),
                "formula_key": val.get("formula_key"),
            }
            for key, val in calc_results.items()
        },
    }
