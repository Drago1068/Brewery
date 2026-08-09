from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import (
    Recipe,
    RecipeIntent,
    RecipeVersion,
    RecipeVersionAdjunct,
    RecipeVersionFermentable,
    RecipeVersionHop,
    RecipeVersionMashStep,
    RecipeVersionTarget,
    RecipeVersionWaterAddition,
    RecipeVersionYeast,
)
from app.domain.enums import AuditAction, RecipeStatus, RecipeVersionStatus
from app.domain.recipe_rules import (
    RecipeVersionRuleError,
    assert_can_activate,
    assert_can_lock,
    assert_editable,
    next_version_number,
)
from app.schemas.recipe import (
    NewRecipeVersion,
    RecipeClone,
    RecipeCreate,
    RecipeUpdate,
    RecipeVersionBody,
)
from app.services.audit import record_audit
from app.services.brewery import get_brewery


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _version_options():
    return (
        selectinload(RecipeVersion.intent),
        selectinload(RecipeVersion.fermentables),
        selectinload(RecipeVersion.hops),
        selectinload(RecipeVersion.yeasts),
        selectinload(RecipeVersion.adjuncts),
        selectinload(RecipeVersion.water_additions),
        selectinload(RecipeVersion.mash_steps),
        selectinload(RecipeVersion.targets),
    )


async def get_recipe(db: AsyncSession, recipe_id: str) -> Recipe:
    recipe = await db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


async def get_version(db: AsyncSession, version_id: str) -> RecipeVersion:
    result = await db.execute(
        select(RecipeVersion).options(*_version_options()).where(RecipeVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="RecipeVersion not found"
        )
    return version


def _populate_version_components(version: RecipeVersion, body: RecipeVersionBody) -> None:
    version.fermentables = [
        RecipeVersionFermentable(
            ingredient_id=line.ingredient_id,
            ingredient_name=line.ingredient_name,
            manufacturer=line.manufacturer,
            amount=line.amount,
            unit=line.unit.value,
            color_lovibond=line.color_lovibond,
            potential_sg=line.potential_sg,
            yield_percent=line.yield_percent,
            sort_order=line.sort_order,
        )
        for line in body.fermentables
    ]
    version.hops = [
        RecipeVersionHop(
            ingredient_id=line.ingredient_id,
            ingredient_name=line.ingredient_name,
            manufacturer=line.manufacturer,
            amount=line.amount,
            unit=line.unit.value,
            alpha_acid=line.alpha_acid,
            stage=line.stage.value,
            time_minutes=line.time_minutes,
            sort_order=line.sort_order,
        )
        for line in body.hops
    ]
    version.yeasts = [
        RecipeVersionYeast(
            ingredient_id=line.ingredient_id,
            ingredient_name=line.ingredient_name,
            manufacturer=line.manufacturer,
            amount=line.amount,
            unit=_enum_value(line.unit) if line.unit else None,
            expected_attenuation=line.expected_attenuation,
            temperature_min_c=line.temperature_min_c,
            temperature_max_c=line.temperature_max_c,
            sort_order=line.sort_order,
        )
        for line in body.yeasts
    ]
    version.adjuncts = [
        RecipeVersionAdjunct(
            ingredient_id=line.ingredient_id,
            ingredient_name=line.ingredient_name,
            amount=line.amount,
            unit=line.unit.value,
            notes=line.notes,
            sort_order=line.sort_order,
        )
        for line in body.adjuncts
    ]
    version.water_additions = [
        RecipeVersionWaterAddition(
            name=line.name,
            amount=line.amount,
            unit=line.unit.value,
            stage=line.stage,
            sort_order=line.sort_order,
        )
        for line in body.water_additions
    ]
    version.mash_steps = [
        RecipeVersionMashStep(
            step_name=line.step_name,
            target_temperature_c=line.target_temperature_c,
            duration_minutes=line.duration_minutes,
            mash_water_volume=line.mash_water_volume,
            mash_water_unit=_enum_value(line.mash_water_unit) if line.mash_water_unit else None,
            sparge_water_volume=line.sparge_water_volume,
            sparge_water_unit=_enum_value(line.sparge_water_unit)
            if line.sparge_water_unit
            else None,
            sort_order=line.sort_order,
        )
        for line in body.mash_steps
    ]
    version.targets = [
        RecipeVersionTarget(
            name=line.name,
            value=line.value,
            unit=line.unit,
            notes=line.notes,
        )
        for line in body.targets
    ]
    if body.intent is not None:
        version.intent = RecipeIntent(**body.intent.model_dump())


def _apply_version_header(version: RecipeVersion, body: RecipeVersionBody) -> None:
    version.batch_size = body.batch_size
    version.batch_size_unit = body.batch_size_unit.value
    version.equipment_profile_id = body.equipment_profile_id
    version.brewhouse_efficiency = body.brewhouse_efficiency
    version.boil_time_minutes = body.boil_time_minutes
    version.mash_method = _enum_value(body.mash_method) if body.mash_method else None
    version.notes = body.notes
    if body.change_summary is not None:
        version.change_summary = body.change_summary


async def list_recipes(db: AsyncSession, brewery_id: str) -> list[Recipe]:
    await get_brewery(db, brewery_id)
    result = await db.execute(
        select(Recipe)
        .where(Recipe.brewery_id == brewery_id)
        .order_by(Recipe.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_recipe_detail(db: AsyncSession, recipe_id: str) -> dict:
    recipe = await get_recipe(db, recipe_id)
    await db.refresh(recipe)
    versions_result = await db.execute(
        select(RecipeVersion)
        .where(RecipeVersion.recipe_id == recipe_id)
        .order_by(RecipeVersion.version_number.asc())
    )
    versions = list(versions_result.scalars().all())
    for version in versions:
        await db.refresh(version)
    current = None
    if recipe.current_version_id:
        current = await get_version(db, recipe.current_version_id)
    return {
        "recipe": recipe,
        "versions": versions,
        "current_version": current,
    }


async def create_recipe(db: AsyncSession, brewery_id: str, payload: RecipeCreate) -> dict:
    await get_brewery(db, brewery_id)
    actor = settings.default_actor_id
    recipe = Recipe(
        brewery_id=brewery_id,
        name=payload.name,
        style=payload.style,
        description=payload.description,
        status=RecipeStatus.ACTIVE.value,
        created_by=actor,
    )
    version = RecipeVersion(
        version_number=1,
        status=RecipeVersionStatus.DRAFT.value,
        created_by=actor,
    )
    _apply_version_header(version, payload.version)
    _populate_version_components(version, payload.version)
    recipe.versions.append(version)
    db.add(recipe)
    await db.flush()
    recipe.current_version_id = version.id
    await record_audit(
        db,
        action=AuditAction.RECIPE_CREATED.value,
        entity_type="recipe",
        entity_id=recipe.id,
        actor_id=actor,
        summary=f"Created recipe '{recipe.name}' with version 1",
        brewery_id=brewery_id,
        details={"version_id": version.id},
    )
    await db.commit()
    return await get_recipe_detail(db, recipe.id)


async def update_recipe(db: AsyncSession, recipe_id: str, payload: RecipeUpdate) -> Recipe:
    recipe = await get_recipe(db, recipe_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(recipe, key, _enum_value(value))
    await db.commit()
    await db.refresh(recipe)
    return recipe


async def update_draft_version(
    db: AsyncSession, version_id: str, body: RecipeVersionBody
) -> RecipeVersion:
    version = await get_version(db, version_id)
    try:
        assert_editable(version.status)
    except RecipeVersionRuleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    _apply_version_header(version, body)
    version.fermentables.clear()
    version.hops.clear()
    version.yeasts.clear()
    version.adjuncts.clear()
    version.water_additions.clear()
    version.mash_steps.clear()
    version.targets.clear()
    if version.intent is not None:
        await db.delete(version.intent)
        await db.flush()
        version.intent = None
    _populate_version_components(version, body)

    actor = settings.default_actor_id
    recipe = await get_recipe(db, version.recipe_id)
    await record_audit(
        db,
        action=AuditAction.RECIPE_VERSION_UPDATED.value,
        entity_type="recipe_version",
        entity_id=version.id,
        actor_id=actor,
        summary=f"Updated draft RecipeVersion {version.version_number}",
        brewery_id=recipe.brewery_id,
    )
    await db.commit()
    return await get_version(db, version.id)


async def create_new_version(
    db: AsyncSession, recipe_id: str, payload: NewRecipeVersion
) -> RecipeVersion:
    recipe = await get_recipe(db, recipe_id)
    result = await db.execute(
        select(RecipeVersion.version_number).where(RecipeVersion.recipe_id == recipe_id)
    )
    numbers = [row[0] for row in result.all()]
    parent_id = recipe.current_version_id
    actor = settings.default_actor_id
    version = RecipeVersion(
        recipe_id=recipe_id,
        version_number=next_version_number(numbers),
        parent_version_id=parent_id,
        status=RecipeVersionStatus.DRAFT.value,
        created_by=actor,
        change_summary=payload.change_summary or payload.version.change_summary,
    )
    _apply_version_header(version, payload.version)
    if payload.change_summary:
        version.change_summary = payload.change_summary
    _populate_version_components(version, payload.version)
    db.add(version)
    await db.flush()
    recipe.current_version_id = version.id
    await record_audit(
        db,
        action=AuditAction.RECIPE_VERSION_CREATED.value,
        entity_type="recipe_version",
        entity_id=version.id,
        actor_id=actor,
        summary=f"Created RecipeVersion {version.version_number} for '{recipe.name}'",
        brewery_id=recipe.brewery_id,
        details={"parent_version_id": parent_id},
    )
    await db.commit()
    return await get_version(db, version.id)


async def activate_version(db: AsyncSession, version_id: str) -> RecipeVersion:
    version = await get_version(db, version_id)
    try:
        assert_can_activate(version.status)
    except RecipeVersionRuleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    recipe = await get_recipe(db, version.recipe_id)
    result = await db.execute(
        select(RecipeVersion).where(
            RecipeVersion.recipe_id == recipe.id,
            RecipeVersion.status == RecipeVersionStatus.ACTIVE.value,
        )
    )
    for prior in result.scalars().all():
        if prior.id != version.id:
            prior.status = RecipeVersionStatus.SUPERSEDED.value

    actor = settings.default_actor_id
    version.status = RecipeVersionStatus.ACTIVE.value
    version.approved_by = actor
    version.approved_at = datetime.now(timezone.utc)
    recipe.current_version_id = version.id
    await record_audit(
        db,
        action=AuditAction.RECIPE_VERSION_ACTIVATED.value,
        entity_type="recipe_version",
        entity_id=version.id,
        actor_id=actor,
        summary=f"Activated RecipeVersion {version.version_number}",
        brewery_id=recipe.brewery_id,
    )
    await db.commit()
    return await get_version(db, version.id)


async def lock_version(db: AsyncSession, version_id: str) -> RecipeVersion:
    version = await get_version(db, version_id)
    try:
        assert_can_lock(version.status)
    except RecipeVersionRuleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    recipe = await get_recipe(db, version.recipe_id)
    version.status = RecipeVersionStatus.LOCKED.value
    actor = settings.default_actor_id
    await record_audit(
        db,
        action=AuditAction.RECIPE_VERSION_LOCKED.value,
        entity_type="recipe_version",
        entity_id=version.id,
        actor_id=actor,
        summary=f"Locked RecipeVersion {version.version_number}",
        brewery_id=recipe.brewery_id,
    )
    await db.commit()
    return await get_version(db, version.id)


def _body_from_version(version: RecipeVersion) -> RecipeVersionBody:
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
    return RecipeVersionBody.model_validate(
        {
            "batch_size": version.batch_size,
            "batch_size_unit": version.batch_size_unit,
            "equipment_profile_id": version.equipment_profile_id,
            "brewhouse_efficiency": version.brewhouse_efficiency,
            "boil_time_minutes": version.boil_time_minutes,
            "mash_method": version.mash_method,
            "notes": version.notes,
            "change_summary": f"Cloned from version {version.version_number}",
            "intent": intent,
            "fermentables": [
                {
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
                {"name": t.name, "value": t.value, "unit": t.unit, "notes": t.notes}
                for t in version.targets
            ],
        }
    )


async def clone_recipe(db: AsyncSession, recipe_id: str, payload: RecipeClone) -> dict:
    source = await get_recipe(db, recipe_id)
    if not source.current_version_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Source recipe has no current version to clone",
        )
    source_version = await get_version(db, source.current_version_id)
    body = _body_from_version(source_version)
    create_payload = RecipeCreate(
        name=payload.name.strip(),
        style=source.style,
        description=source.description,
        version=body,
    )
    detail = await create_recipe(db, source.brewery_id, create_payload)
    actor = settings.default_actor_id
    await record_audit(
        db,
        action=AuditAction.RECIPE_CLONED.value,
        entity_type="recipe",
        entity_id=detail["recipe"].id,
        actor_id=actor,
        summary=f"Cloned recipe '{source.name}' → '{payload.name}'",
        brewery_id=source.brewery_id,
        details={"source_recipe_id": source.id, "source_version_id": source_version.id},
    )
    await db.commit()
    return detail
