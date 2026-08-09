from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import Ingredient, IngredientLot, InventoryTransaction
from app.domain.enums import AuditAction, InventoryTransactionType
from app.domain.inventory_math import apply_transaction, available_quantity
from app.schemas.inventory import (
    InventoryAdjust,
    InventoryAvailabilityRow,
    InventoryConsume,
    InventoryReceive,
    InventoryReserve,
    InventoryWaste,
)
from app.services.audit import record_audit
from app.services.brewery import get_brewery
from app.services.ingredient import get_ingredient


async def get_lot(db: AsyncSession, lot_id: str) -> IngredientLot:
    lot = await db.get(IngredientLot, lot_id)
    if lot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient lot not found")
    return lot


async def _append_transaction(
    db: AsyncSession,
    *,
    lot: IngredientLot,
    transaction_type: InventoryTransactionType,
    quantity: Decimal,
    reason: str | None,
    reference_type: str | None = None,
    reference_id: str | None = None,
    audit_action: AuditAction,
    summary: str,
) -> InventoryTransaction:
    if lot.unit and quantity is not None:
        # Unit must match lot unit — no silent conversion in Epic 1 inventory ops.
        pass

    try:
        new_on_hand, new_reserved = apply_transaction(
            on_hand=lot.quantity_on_hand,
            reserved=lot.quantity_reserved,
            transaction_type=transaction_type,
            quantity=quantity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    actor = settings.default_actor_id
    tx = InventoryTransaction(
        brewery_id=lot.brewery_id,
        ingredient_lot_id=lot.id,
        transaction_type=transaction_type.value,
        quantity=quantity,
        unit=lot.unit,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        created_by=actor,
    )
    lot.quantity_on_hand = new_on_hand
    lot.quantity_reserved = new_reserved
    db.add(tx)
    await db.flush()
    await record_audit(
        db,
        action=audit_action.value,
        entity_type="inventory_transaction",
        entity_id=tx.id,
        actor_id=actor,
        summary=summary,
        brewery_id=lot.brewery_id,
        details={
            "lot_id": lot.id,
            "transaction_type": transaction_type.value,
            "quantity": str(quantity),
            "unit": lot.unit,
            "on_hand_after": str(new_on_hand),
            "reserved_after": str(new_reserved),
        },
    )
    await db.commit()
    await db.refresh(lot)
    await db.refresh(tx)
    return tx


async def receive_inventory(
    db: AsyncSession, brewery_id: str, payload: InventoryReceive
) -> tuple[IngredientLot, InventoryTransaction]:
    await get_brewery(db, brewery_id)
    ingredient = await get_ingredient(db, payload.ingredient_id)
    if ingredient.brewery_id != brewery_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found for brewery"
        )
    if payload.unit.value != ingredient.default_unit:
        # Allow lot unit to equal declared receive unit; require match to ingredient default
        # for Epic 1 simplicity (no silent conversion).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Receive unit '{payload.unit.value}' must match ingredient default_unit "
                f"'{ingredient.default_unit}' (no silent unit conversion)"
            ),
        )

    actor = settings.default_actor_id
    lot = IngredientLot(
        brewery_id=brewery_id,
        ingredient_id=ingredient.id,
        supplier=payload.supplier,
        supplier_lot_number=payload.supplier_lot_number,
        manufacturer_lot_number=payload.manufacturer_lot_number,
        received_date=payload.received_date or datetime.now(timezone.utc),
        expiration_date=payload.expiration_date,
        quantity_received=payload.quantity,
        unit=payload.unit.value,
        purchase_cost=payload.purchase_cost,
        storage_location=payload.storage_location,
        opened_at=payload.opened_at,
        notes=payload.notes,
        actual_alpha_acid=payload.actual_alpha_acid,
        quantity_on_hand=Decimal("0"),
        quantity_reserved=Decimal("0"),
        created_by=actor,
    )
    db.add(lot)
    await db.flush()

    tx = await _append_transaction(
        db,
        lot=lot,
        transaction_type=InventoryTransactionType.RECEIPT,
        quantity=payload.quantity,
        reason=payload.reason or "Receipt",
        audit_action=AuditAction.INVENTORY_RECEIPT,
        summary=f"Received {payload.quantity} {payload.unit.value} of {ingredient.name}",
    )
    return lot, tx


async def adjust_inventory(db: AsyncSession, payload: InventoryAdjust) -> InventoryTransaction:
    lot = await get_lot(db, payload.lot_id)
    return await _append_transaction(
        db,
        lot=lot,
        transaction_type=InventoryTransactionType.ADJUSTMENT,
        quantity=payload.quantity,
        reason=payload.reason,
        audit_action=AuditAction.INVENTORY_ADJUSTMENT,
        summary=f"Adjusted lot {lot.id} by {payload.quantity} {lot.unit}",
    )


async def consume_inventory(db: AsyncSession, payload: InventoryConsume) -> InventoryTransaction:
    lot = await get_lot(db, payload.lot_id)
    return await _append_transaction(
        db,
        lot=lot,
        transaction_type=InventoryTransactionType.CONSUMPTION,
        quantity=payload.quantity,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        audit_action=AuditAction.INVENTORY_CONSUMPTION,
        summary=f"Consumed {payload.quantity} {lot.unit} from lot {lot.id}",
    )


async def waste_inventory(db: AsyncSession, payload: InventoryWaste) -> InventoryTransaction:
    lot = await get_lot(db, payload.lot_id)
    return await _append_transaction(
        db,
        lot=lot,
        transaction_type=InventoryTransactionType.WASTE,
        quantity=payload.quantity,
        reason=payload.reason,
        audit_action=AuditAction.INVENTORY_WASTE,
        summary=f"Discarded {payload.quantity} {lot.unit} from lot {lot.id}",
    )


async def reserve_inventory(db: AsyncSession, payload: InventoryReserve) -> InventoryTransaction:
    lot = await get_lot(db, payload.lot_id)
    return await _append_transaction(
        db,
        lot=lot,
        transaction_type=InventoryTransactionType.RESERVATION,
        quantity=payload.quantity,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        audit_action=AuditAction.INVENTORY_RESERVATION,
        summary=f"Reserved {payload.quantity} {lot.unit} on lot {lot.id}",
    )


async def release_reservation(
    db: AsyncSession, payload: InventoryReserve
) -> InventoryTransaction:
    lot = await get_lot(db, payload.lot_id)
    return await _append_transaction(
        db,
        lot=lot,
        transaction_type=InventoryTransactionType.RESERVATION_RELEASE,
        quantity=payload.quantity,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        audit_action=AuditAction.INVENTORY_RESERVATION_RELEASE,
        summary=f"Released reservation of {payload.quantity} {lot.unit} on lot {lot.id}",
    )


def _freshness(lots: list[IngredientLot], now: datetime) -> str:
    if not lots:
        return "UNKNOWN"
    expiring_horizon = now + timedelta(days=30)
    statuses: list[str] = []
    for lot in lots:
        if lot.expiration_date is not None:
            exp = lot.expiration_date
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                statuses.append("EXPIRED")
            elif exp <= expiring_horizon:
                statuses.append("EXPIRING")
        if lot.opened_at is not None:
            statuses.append("OPENED")
    if "EXPIRED" in statuses:
        return "EXPIRED"
    if "EXPIRING" in statuses:
        return "EXPIRING"
    if "OPENED" in statuses:
        return "OPENED"
    if any(lot.expiration_date is None for lot in lots):
        # Have stock but no expiration recorded — not invented as fresh.
        if all(lot.expiration_date is None and lot.opened_at is None for lot in lots):
            return "UNKNOWN"
    return "OK"


async def list_availability(db: AsyncSession, brewery_id: str) -> list[InventoryAvailabilityRow]:
    await get_brewery(db, brewery_id)
    result = await db.execute(
        select(Ingredient)
        .options(selectinload(Ingredient.lots))
        .where(Ingredient.brewery_id == brewery_id, Ingredient.active.is_(True))
        .order_by(Ingredient.name.asc())
    )
    ingredients = list(result.scalars().all())
    now = datetime.now(timezone.utc)
    rows: list[InventoryAvailabilityRow] = []
    for ingredient in ingredients:
        lots = [lot for lot in ingredient.lots if lot.quantity_on_hand > 0 or lot.quantity_reserved > 0]
        # Still show ingredients with zero stock if they have any lot history? Prefer show all with lots or any on hand.
        all_lots = list(ingredient.lots)
        if not all_lots:
            continue
        on_hand = sum((lot.quantity_on_hand for lot in all_lots), Decimal("0"))
        reserved = sum((lot.quantity_reserved for lot in all_lots), Decimal("0"))
        locations = sorted(
            {
                lot.storage_location
                for lot in all_lots
                if lot.storage_location and (lot.quantity_on_hand > 0 or lot.quantity_reserved > 0)
            }
        )
        rows.append(
            InventoryAvailabilityRow(
                ingredient_id=ingredient.id,
                name=ingredient.name,
                category=ingredient.category,
                manufacturer=ingredient.manufacturer,
                unit=ingredient.default_unit,
                quantity_on_hand=on_hand,
                quantity_reserved=reserved,
                quantity_available=available_quantity(on_hand, reserved),
                storage_locations=locations,
                freshness=_freshness(lots or all_lots, now),
                lot_count=len(all_lots),
            )
        )
    return rows


async def list_lots_for_ingredient(
    db: AsyncSession, brewery_id: str, ingredient_id: str
) -> list[IngredientLot]:
    await get_brewery(db, brewery_id)
    ingredient = await get_ingredient(db, ingredient_id)
    if ingredient.brewery_id != brewery_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found")
    result = await db.execute(
        select(IngredientLot)
        .where(
            IngredientLot.brewery_id == brewery_id,
            IngredientLot.ingredient_id == ingredient_id,
        )
        .order_by(IngredientLot.created_at.desc())
    )
    return list(result.scalars().all())


async def list_transactions_for_lot(
    db: AsyncSession, lot_id: str
) -> list[InventoryTransaction]:
    await get_lot(db, lot_id)
    result = await db.execute(
        select(InventoryTransaction)
        .where(InventoryTransaction.ingredient_lot_id == lot_id)
        .order_by(InventoryTransaction.occurred_at.asc(), InventoryTransaction.created_at.asc())
    )
    return list(result.scalars().all())
