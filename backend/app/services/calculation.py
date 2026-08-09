from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.recipe_calculator import calculate_recipe
from app.calculations.registry import list_formulas
from app.calculations.scaling import scale_recipe
from app.services.recipe import get_version


async def calculate_version(db: AsyncSession, version_id: str) -> dict:
    version = await get_version(db, version_id)
    payload = {
        "batch_size": version.batch_size,
        "batch_size_unit": version.batch_size_unit,
        "brewhouse_efficiency": version.brewhouse_efficiency,
        "fermentables": [
            {
                "ingredient_name": f.ingredient_name,
                "amount": f.amount,
                "unit": f.unit,
                "potential_sg": f.potential_sg,
                "color_lovibond": f.color_lovibond,
            }
            for f in version.fermentables
        ],
        "hops": [
            {
                "ingredient_name": h.ingredient_name,
                "amount": h.amount,
                "unit": h.unit,
                "alpha_acid": h.alpha_acid,
                "stage": h.stage,
                "time_minutes": h.time_minutes,
            }
            for h in version.hops
        ],
        "yeasts": [
            {
                "ingredient_name": y.ingredient_name,
                "expected_attenuation": y.expected_attenuation,
            }
            for y in version.yeasts
        ],
        "mash_steps": [
            {
                "target_temperature_c": m.target_temperature_c,
                "duration_minutes": m.duration_minutes,
                "mash_water_volume": m.mash_water_volume,
                "mash_water_unit": m.mash_water_unit,
                "sparge_water_volume": m.sparge_water_volume,
                "sparge_water_unit": m.sparge_water_unit,
            }
            for m in version.mash_steps
        ],
        # Equipment losses are optional — never silently defaulted.
        "boil_off": None,
        "boil_off_unit": None,
        "trub_loss": None,
        "trub_loss_unit": None,
        "grain_temp_c": None,
    }
    if version.equipment_profile_id:
        from decimal import Decimal

        from app.db.models import EquipmentProfile

        equipment = await db.get(EquipmentProfile, version.equipment_profile_id)
        if equipment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment profile referenced by recipe was not found",
            )
        # boil_off_rate is a rate — convert to volume only when boil time is known.
        rate_unit = equipment.boil_off_rate_unit or ""
        if (
            equipment.boil_off_rate is not None
            and version.boil_time_minutes is not None
            and rate_unit.endswith("/hr")
        ):
            hours = Decimal(version.boil_time_minutes) / Decimal("60")
            payload["boil_off"] = equipment.boil_off_rate * hours
            payload["boil_off_unit"] = rate_unit[: -len("/hr")]
        payload["trub_loss"] = equipment.trub_loss
        payload["trub_loss_unit"] = equipment.trub_loss_unit
        if version.brewhouse_efficiency is None and equipment.typical_brewhouse_efficiency is not None:
            payload["brewhouse_efficiency"] = equipment.typical_brewhouse_efficiency

    return {
        "recipe_version_id": version.id,
        "recipe_id": version.recipe_id,
        "version_number": version.version_number,
        **calculate_recipe(payload),
    }


def formulas_catalog() -> list[dict]:
    return list_formulas()


def scale_amounts(payload: dict) -> dict:
    result = scale_recipe(
        from_batch_size=payload.get("from_batch_size"),
        from_batch_unit=payload.get("from_batch_unit"),
        to_batch_size=payload.get("to_batch_size"),
        to_batch_unit=payload.get("to_batch_unit"),
        amounts=payload.get("amounts") or [],
    )
    return result.to_dict()
