from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.brewery import BreweryCreate, BreweryRead, BreweryUpdate
from app.services import brewery as brewery_service

router = APIRouter(prefix="/brewery", tags=["brewery"])


@router.get("", response_model=BreweryRead | None)
async def get_brewery(db: AsyncSession = Depends(get_db)):
    """Return the primary brewery, or null if setup has not run."""
    return await brewery_service.get_primary_brewery(db)


@router.get("/{brewery_id}", response_model=BreweryRead)
async def get_brewery_by_id(brewery_id: str, db: AsyncSession = Depends(get_db)):
    return await brewery_service.get_brewery(db, brewery_id)


@router.post("", response_model=BreweryRead, status_code=201)
async def create_brewery(payload: BreweryCreate, db: AsyncSession = Depends(get_db)):
    return await brewery_service.create_brewery(db, payload)


@router.patch("/{brewery_id}", response_model=BreweryRead)
async def update_brewery(
    brewery_id: str, payload: BreweryUpdate, db: AsyncSession = Depends(get_db)
):
    return await brewery_service.update_brewery(db, brewery_id, payload)
