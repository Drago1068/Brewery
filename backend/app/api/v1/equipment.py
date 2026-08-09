from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.brewery import EquipmentCreate, EquipmentRead, EquipmentUpdate
from app.services import equipment as equipment_service

router = APIRouter(tags=["equipment"])


@router.get("/breweries/{brewery_id}/equipment", response_model=list[EquipmentRead])
async def list_equipment(brewery_id: str, db: AsyncSession = Depends(get_db)):
    return await equipment_service.list_equipment(db, brewery_id)


@router.post(
    "/breweries/{brewery_id}/equipment",
    response_model=EquipmentRead,
    status_code=201,
)
async def create_equipment(
    brewery_id: str, payload: EquipmentCreate, db: AsyncSession = Depends(get_db)
):
    return await equipment_service.create_equipment(db, brewery_id, payload)


@router.get("/equipment/{equipment_id}", response_model=EquipmentRead)
async def get_equipment(equipment_id: str, db: AsyncSession = Depends(get_db)):
    return await equipment_service.get_equipment(db, equipment_id)


@router.patch("/equipment/{equipment_id}", response_model=EquipmentRead)
async def update_equipment(
    equipment_id: str, payload: EquipmentUpdate, db: AsyncSession = Depends(get_db)
):
    return await equipment_service.update_equipment(db, equipment_id, payload)
