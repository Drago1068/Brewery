from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.recipe import (
    NewRecipeVersion,
    RecipeClone,
    RecipeCreate,
    RecipeDetail,
    RecipeRead,
    RecipeUpdate,
    RecipeVersionBody,
    RecipeVersionRead,
    RecipeVersionSummary,
)
from app.services import recipe as recipe_service

router = APIRouter(tags=["recipes"])


def _to_detail(payload: dict) -> RecipeDetail:
    recipe = payload["recipe"]
    versions = payload["versions"]
    current = payload["current_version"]
    return RecipeDetail(
        id=recipe.id,
        brewery_id=recipe.brewery_id,
        name=recipe.name,
        style=recipe.style,
        description=recipe.description,
        status=recipe.status,
        current_version_id=recipe.current_version_id,
        created_by=recipe.created_by,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
        current_version=RecipeVersionRead.model_validate(current) if current else None,
        versions=[RecipeVersionSummary.model_validate(v) for v in versions],
    )


@router.get("/breweries/{brewery_id}/recipes", response_model=list[RecipeRead])
async def list_recipes(brewery_id: str, db: AsyncSession = Depends(get_db)):
    return await recipe_service.list_recipes(db, brewery_id)


@router.post("/breweries/{brewery_id}/recipes", response_model=RecipeDetail, status_code=201)
async def create_recipe(
    brewery_id: str, payload: RecipeCreate, db: AsyncSession = Depends(get_db)
):
    detail = await recipe_service.create_recipe(db, brewery_id, payload)
    return _to_detail(detail)


@router.get("/recipes/{recipe_id}", response_model=RecipeDetail)
async def get_recipe(recipe_id: str, db: AsyncSession = Depends(get_db)):
    detail = await recipe_service.get_recipe_detail(db, recipe_id)
    return _to_detail(detail)


@router.patch("/recipes/{recipe_id}", response_model=RecipeRead)
async def update_recipe(
    recipe_id: str, payload: RecipeUpdate, db: AsyncSession = Depends(get_db)
):
    return await recipe_service.update_recipe(db, recipe_id, payload)


@router.post("/recipes/{recipe_id}/versions", response_model=RecipeVersionRead, status_code=201)
async def create_version(
    recipe_id: str, payload: NewRecipeVersion, db: AsyncSession = Depends(get_db)
):
    return await recipe_service.create_new_version(db, recipe_id, payload)


@router.put("/recipe-versions/{version_id}", response_model=RecipeVersionRead)
async def update_draft_version(
    version_id: str, payload: RecipeVersionBody, db: AsyncSession = Depends(get_db)
):
    return await recipe_service.update_draft_version(db, version_id, payload)


@router.get("/recipe-versions/{version_id}", response_model=RecipeVersionRead)
async def get_version(version_id: str, db: AsyncSession = Depends(get_db)):
    return await recipe_service.get_version(db, version_id)


@router.post("/recipe-versions/{version_id}/activate", response_model=RecipeVersionRead)
async def activate_version(version_id: str, db: AsyncSession = Depends(get_db)):
    return await recipe_service.activate_version(db, version_id)


@router.post("/recipe-versions/{version_id}/lock", response_model=RecipeVersionRead)
async def lock_version(version_id: str, db: AsyncSession = Depends(get_db)):
    return await recipe_service.lock_version(db, version_id)


@router.post("/recipes/{recipe_id}/clone", response_model=RecipeDetail, status_code=201)
async def clone_recipe(
    recipe_id: str, payload: RecipeClone, db: AsyncSession = Depends(get_db)
):
    detail = await recipe_service.clone_recipe(db, recipe_id, payload)
    return _to_detail(detail)
