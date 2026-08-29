from fastapi import APIRouter, status

from brewing_api.application import recipes as service
from brewing_api.presentation.dependencies import CurrentUser, Db
from brewing_api.presentation.schemas import RecipeCreate, RecipeResponse

router = APIRouter(prefix="/recipes", tags=["recipes"])


def serialize(recipe: object, version: object) -> RecipeResponse:
    return RecipeResponse(
        id=recipe.id,
        name=recipe.name,
        version_id=version.id,
        version_number=version.version_number,
        target_mash_temperature=version.target_mash_temperature,
        mash_temperature_unit=version.mash_temperature_unit,
        target_mash_ph=version.target_mash_ph,
        mash_ph_tolerance=version.mash_ph_tolerance,
        target_mash_gravity=version.target_mash_gravity,
        mash_gravity_tolerance=version.mash_gravity_tolerance,
        planned_mash_duration_minutes=version.planned_mash_duration_minutes,
    )


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create(command: RecipeCreate, db: Db, user: CurrentUser) -> RecipeResponse:
    recipe, version = service.create_recipe(db, user, command)
    return serialize(recipe, version)


@router.get("", response_model=list[RecipeResponse])
def list_recipes(db: Db, user: CurrentUser) -> list[RecipeResponse]:
    return [serialize(recipe, version) for recipe, version in service.list_owned_recipes(db, user)]
