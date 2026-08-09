from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    FermentableProfile,
    HopProfile,
    Ingredient,
    YeastProfile,
)
from app.domain.enums import IngredientCategory
from app.schemas.inventory import IngredientCreate, IngredientUpdate
from app.services.brewery import get_brewery


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _ingredient_options():
    return (
        selectinload(Ingredient.fermentable_profile),
        selectinload(Ingredient.hop_profile),
        selectinload(Ingredient.yeast_profile),
    )


async def get_ingredient(db: AsyncSession, ingredient_id: str) -> Ingredient:
    result = await db.execute(
        select(Ingredient)
        .options(*_ingredient_options())
        .where(Ingredient.id == ingredient_id)
    )
    ingredient = result.scalar_one_or_none()
    if ingredient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found")
    return ingredient


async def search_ingredients(
    db: AsyncSession,
    brewery_id: str,
    *,
    q: str | None = None,
    category: IngredientCategory | None = None,
    active_only: bool = True,
) -> list[Ingredient]:
    await get_brewery(db, brewery_id)
    stmt = (
        select(Ingredient)
        .options(*_ingredient_options())
        .where(Ingredient.brewery_id == brewery_id)
    )
    if active_only:
        stmt = stmt.where(Ingredient.active.is_(True))
    if category is not None:
        stmt = stmt.where(Ingredient.category == category.value)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Ingredient.name.ilike(pattern),
                Ingredient.manufacturer.ilike(pattern),
                Ingredient.description.ilike(pattern),
            )
        )
    stmt = stmt.order_by(Ingredient.category.asc(), Ingredient.name.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _attach_profiles(ingredient: Ingredient, payload: IngredientCreate | IngredientUpdate) -> None:
    if getattr(payload, "fermentable_profile", None) is not None and payload.fermentable_profile:
        fp = payload.fermentable_profile
        ingredient.fermentable_profile = FermentableProfile(
            fermentable_type=fp.fermentable_type.value,
            color_lovibond=fp.color_lovibond,
            potential_sg=fp.potential_sg,
            yield_percent=fp.yield_percent,
        )
    if getattr(payload, "hop_profile", None) is not None and payload.hop_profile:
        hp = payload.hop_profile
        ingredient.hop_profile = HopProfile(
            hop_type=hp.hop_type.value,
            default_alpha_acid=hp.default_alpha_acid,
            beta_acid=hp.beta_acid,
            aroma_descriptors=hp.aroma_descriptors,
        )
    if getattr(payload, "yeast_profile", None) is not None and payload.yeast_profile:
        yp = payload.yeast_profile
        ingredient.yeast_profile = YeastProfile(
            yeast_type=yp.yeast_type.value,
            strain=yp.strain,
            attenuation_min=yp.attenuation_min,
            attenuation_max=yp.attenuation_max,
            temperature_min_c=yp.temperature_min_c,
            temperature_max_c=yp.temperature_max_c,
        )


async def create_ingredient(
    db: AsyncSession, brewery_id: str, payload: IngredientCreate
) -> Ingredient:
    await get_brewery(db, brewery_id)
    actor = settings.default_actor_id
    ingredient = Ingredient(
        brewery_id=brewery_id,
        category=payload.category.value,
        name=payload.name,
        manufacturer=payload.manufacturer,
        description=payload.description,
        default_unit=payload.default_unit.value,
        active=payload.active,
        created_by=actor,
    )
    _attach_profiles(ingredient, payload)
    db.add(ingredient)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An ingredient with this category and name already exists",
        ) from exc
    return await get_ingredient(db, ingredient.id)


async def update_ingredient(
    db: AsyncSession, ingredient_id: str, payload: IngredientUpdate
) -> Ingredient:
    ingredient = await get_ingredient(db, ingredient_id)
    data = payload.model_dump(exclude_unset=True, exclude={"fermentable_profile", "hop_profile", "yeast_profile"})
    for key, value in data.items():
        setattr(ingredient, key, _enum_value(value))

    if payload.fermentable_profile is not None:
        if ingredient.category != IngredientCategory.FERMENTABLE.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="fermentable_profile only valid for FERMENTABLE",
            )
        fp = payload.fermentable_profile
        if ingredient.fermentable_profile is None:
            ingredient.fermentable_profile = FermentableProfile(ingredient_id=ingredient.id)
        ingredient.fermentable_profile.fermentable_type = fp.fermentable_type.value
        ingredient.fermentable_profile.color_lovibond = fp.color_lovibond
        ingredient.fermentable_profile.potential_sg = fp.potential_sg
        ingredient.fermentable_profile.yield_percent = fp.yield_percent

    if payload.hop_profile is not None:
        if ingredient.category != IngredientCategory.HOP.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="hop_profile only valid for HOP",
            )
        hp = payload.hop_profile
        if ingredient.hop_profile is None:
            ingredient.hop_profile = HopProfile(ingredient_id=ingredient.id)
        ingredient.hop_profile.hop_type = hp.hop_type.value
        ingredient.hop_profile.default_alpha_acid = hp.default_alpha_acid
        ingredient.hop_profile.beta_acid = hp.beta_acid
        ingredient.hop_profile.aroma_descriptors = hp.aroma_descriptors

    if payload.yeast_profile is not None:
        if ingredient.category != IngredientCategory.YEAST.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="yeast_profile only valid for YEAST",
            )
        yp = payload.yeast_profile
        if ingredient.yeast_profile is None:
            ingredient.yeast_profile = YeastProfile(ingredient_id=ingredient.id)
        ingredient.yeast_profile.yeast_type = yp.yeast_type.value
        ingredient.yeast_profile.strain = yp.strain
        ingredient.yeast_profile.attenuation_min = yp.attenuation_min
        ingredient.yeast_profile.attenuation_max = yp.attenuation_max
        ingredient.yeast_profile.temperature_min_c = yp.temperature_min_c
        ingredient.yeast_profile.temperature_max_c = yp.temperature_max_c

    ingredient.updated_by = settings.default_actor_id
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An ingredient with this category and name already exists",
        ) from exc
    return await get_ingredient(db, ingredient.id)
