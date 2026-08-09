from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domain.enums import IngredientCategory
from app.schemas.inventory import IngredientCreate, IngredientRead, IngredientUpdate
from app.services import ingredient as ingredient_service

router = APIRouter(tags=["ingredients"])


@router.get("/breweries/{brewery_id}/ingredients", response_model=list[IngredientRead])
async def search_ingredients(
    brewery_id: str,
    q: str | None = Query(default=None),
    category: IngredientCategory | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    return await ingredient_service.search_ingredients(
        db, brewery_id, q=q, category=category, active_only=active_only
    )


@router.post(
    "/breweries/{brewery_id}/ingredients",
    response_model=IngredientRead,
    status_code=201,
)
async def create_ingredient(
    brewery_id: str, payload: IngredientCreate, db: AsyncSession = Depends(get_db)
):
    return await ingredient_service.create_ingredient(db, brewery_id, payload)


@router.get("/ingredients/{ingredient_id}", response_model=IngredientRead)
async def get_ingredient(ingredient_id: str, db: AsyncSession = Depends(get_db)):
    return await ingredient_service.get_ingredient(db, ingredient_id)


@router.patch("/ingredients/{ingredient_id}", response_model=IngredientRead)
async def update_ingredient(
    ingredient_id: str, payload: IngredientUpdate, db: AsyncSession = Depends(get_db)
):
    return await ingredient_service.update_ingredient(db, ingredient_id, payload)
