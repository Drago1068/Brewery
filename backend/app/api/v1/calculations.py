from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import calculation as calculation_service

router = APIRouter(tags=["calculations"])


class ScaleRequest(BaseModel):
    from_batch_size: Decimal
    from_batch_unit: str
    to_batch_size: Decimal
    to_batch_unit: str
    amounts: list[dict[str, Any]] = Field(default_factory=list)


class PreviewRequest(BaseModel):
    """Calculate from an in-memory formulation (editor preview) without persisting."""

    batch_size: Decimal
    batch_size_unit: str
    brewhouse_efficiency: Optional[Decimal] = None
    fermentables: list[dict[str, Any]] = Field(default_factory=list)
    hops: list[dict[str, Any]] = Field(default_factory=list)
    yeasts: list[dict[str, Any]] = Field(default_factory=list)
    mash_steps: list[dict[str, Any]] = Field(default_factory=list)
    boil_off: Optional[Decimal] = None
    boil_off_unit: Optional[str] = None
    trub_loss: Optional[Decimal] = None
    trub_loss_unit: Optional[str] = None
    grain_temp_c: Optional[Decimal] = None


@router.get("/calculations/formulas")
async def list_formulas():
    return calculation_service.formulas_catalog()


@router.post("/recipe-versions/{version_id}/calculate")
async def calculate_version(version_id: str, db: AsyncSession = Depends(get_db)):
    return await calculation_service.calculate_version(db, version_id)


@router.post("/calculations/preview")
async def preview_calculation(payload: PreviewRequest):
    from app.calculations.recipe_calculator import calculate_recipe

    return calculate_recipe(payload.model_dump())


@router.post("/calculations/scale")
async def scale(payload: ScaleRequest):
    return calculation_service.scale_amounts(payload.model_dump())
