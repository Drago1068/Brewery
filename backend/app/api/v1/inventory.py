from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.inventory import (
    InventoryAdjust,
    InventoryAvailabilityRow,
    InventoryConsume,
    InventoryReceive,
    InventoryReserve,
    InventoryWaste,
    LotRead,
    TransactionRead,
)
from app.services import inventory as inventory_service

router = APIRouter(tags=["inventory"])


@router.get(
    "/breweries/{brewery_id}/inventory",
    response_model=list[InventoryAvailabilityRow],
)
async def list_inventory(brewery_id: str, db: AsyncSession = Depends(get_db)):
    return await inventory_service.list_availability(db, brewery_id)


@router.post(
    "/breweries/{brewery_id}/inventory/receive",
    response_model=LotRead,
    status_code=201,
)
async def receive_inventory(
    brewery_id: str, payload: InventoryReceive, db: AsyncSession = Depends(get_db)
):
    lot, _tx = await inventory_service.receive_inventory(db, brewery_id, payload)
    return lot


@router.post("/inventory/adjust", response_model=TransactionRead)
async def adjust_inventory(payload: InventoryAdjust, db: AsyncSession = Depends(get_db)):
    return await inventory_service.adjust_inventory(db, payload)


@router.post("/inventory/use", response_model=TransactionRead)
async def consume_inventory(payload: InventoryConsume, db: AsyncSession = Depends(get_db)):
    return await inventory_service.consume_inventory(db, payload)


@router.post("/inventory/discard", response_model=TransactionRead)
async def waste_inventory(payload: InventoryWaste, db: AsyncSession = Depends(get_db)):
    return await inventory_service.waste_inventory(db, payload)


@router.post("/inventory/reserve", response_model=TransactionRead)
async def reserve_inventory(payload: InventoryReserve, db: AsyncSession = Depends(get_db)):
    return await inventory_service.reserve_inventory(db, payload)


@router.post("/inventory/release-reservation", response_model=TransactionRead)
async def release_reservation(payload: InventoryReserve, db: AsyncSession = Depends(get_db)):
    return await inventory_service.release_reservation(db, payload)


@router.get(
    "/breweries/{brewery_id}/ingredients/{ingredient_id}/lots",
    response_model=list[LotRead],
)
async def list_lots(brewery_id: str, ingredient_id: str, db: AsyncSession = Depends(get_db)):
    return await inventory_service.list_lots_for_ingredient(db, brewery_id, ingredient_id)


@router.get("/inventory/lots/{lot_id}/transactions", response_model=list[TransactionRead])
async def list_lot_transactions(lot_id: str, db: AsyncSession = Depends(get_db)):
    return await inventory_service.list_transactions_for_lot(db, lot_id)
