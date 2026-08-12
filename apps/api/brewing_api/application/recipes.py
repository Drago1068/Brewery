import uuid
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from brewing_api.application.errors import NotFoundError
from brewing_api.application.events import audit
from brewing_api.domain.identity.models import User
from brewing_api.domain.recipes.models import Recipe, RecipeVersion


class RecipeCommand(Protocol):
    name: str
    target_mash_temperature: object
    target_mash_ph: object
    mash_ph_tolerance: object
    target_mash_gravity: object
    mash_gravity_tolerance: object
    planned_mash_duration_minutes: int


def create_recipe(db: Session, user: User, command: RecipeCommand) -> tuple[Recipe, RecipeVersion]:
    recipe = Recipe(owner_id=user.id, name=command.name.strip())
    db.add(recipe)
    db.flush()
    version = RecipeVersion(
        recipe_id=recipe.id,
        version_number=1,
        target_mash_temperature=command.target_mash_temperature,
        mash_temperature_unit="degF",
        target_mash_ph=command.target_mash_ph,
        mash_ph_tolerance=command.mash_ph_tolerance,
        target_mash_gravity=command.target_mash_gravity,
        mash_gravity_tolerance=command.mash_gravity_tolerance,
        planned_mash_duration_minutes=command.planned_mash_duration_minutes,
    )
    db.add(version)
    db.flush()
    audit(db, user.id, "RECIPE_CREATED", "Recipe", recipe.id, {"name": recipe.name})
    audit(
        db,
        user.id,
        "RECIPE_VERSION_CREATED",
        "RecipeVersion",
        version.id,
        {"version_number": 1},
    )
    db.commit()
    db.refresh(recipe)
    db.refresh(version)
    return recipe, version


def get_owned_version(db: Session, user: User, version_id: uuid.UUID) -> RecipeVersion:
    version = db.scalar(
        select(RecipeVersion)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .where(RecipeVersion.id == version_id, Recipe.owner_id == user.id)
    )
    if version is None:
        raise NotFoundError("Recipe version not found")
    return version


def list_owned_recipes(db: Session, user: User) -> list[tuple[Recipe, RecipeVersion]]:
    latest = (
        select(
            RecipeVersion.recipe_id,
            func.max(RecipeVersion.version_number).label("version_number"),
        )
        .group_by(RecipeVersion.recipe_id)
        .subquery()
    )
    return list(
        db.execute(
            select(Recipe, RecipeVersion)
            .join(latest, latest.c.recipe_id == Recipe.id)
            .join(
                RecipeVersion,
                (RecipeVersion.recipe_id == latest.c.recipe_id)
                & (RecipeVersion.version_number == latest.c.version_number),
            )
            .where(Recipe.owner_id == user.id)
            .order_by(Recipe.created_at.desc())
        ).all()
    )
