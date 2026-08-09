from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import EquipmentProfile
from app.domain.enums import AuditAction
from app.schemas.brewery import EquipmentCreate, EquipmentUpdate
from app.services.audit import record_audit
from app.services.brewery import get_brewery


async def list_equipment(db: AsyncSession, brewery_id: str) -> list[EquipmentProfile]:
    await get_brewery(db, brewery_id)
    result = await db.execute(
        select(EquipmentProfile)
        .where(EquipmentProfile.brewery_id == brewery_id)
        .order_by(EquipmentProfile.name.asc())
    )
    return list(result.scalars().all())


async def get_equipment(db: AsyncSession, equipment_id: str) -> EquipmentProfile:
    equipment = await db.get(EquipmentProfile, equipment_id)
    if equipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Equipment profile not found"
        )
    return equipment


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


async def create_equipment(
    db: AsyncSession, brewery_id: str, payload: EquipmentCreate
) -> EquipmentProfile:
    await get_brewery(db, brewery_id)
    actor = settings.default_actor_id
    equipment = EquipmentProfile(
        brewery_id=brewery_id,
        name=payload.name,
        system_type=payload.system_type.value,
        target_batch_size=payload.target_batch_size,
        target_batch_size_unit=payload.target_batch_size_unit.value,
        kettle_capacity=payload.kettle_capacity,
        kettle_capacity_unit=payload.kettle_capacity_unit.value,
        mash_capacity=payload.mash_capacity,
        mash_capacity_unit=_enum_value(payload.mash_capacity_unit)
        if payload.mash_capacity_unit
        else None,
        boil_off_rate=payload.boil_off_rate,
        boil_off_rate_unit=payload.boil_off_rate_unit,
        trub_loss=payload.trub_loss,
        trub_loss_unit=_enum_value(payload.trub_loss_unit) if payload.trub_loss_unit else None,
        fermenter_loss=payload.fermenter_loss,
        fermenter_loss_unit=_enum_value(payload.fermenter_loss_unit)
        if payload.fermenter_loss_unit
        else None,
        typical_brewhouse_efficiency=payload.typical_brewhouse_efficiency,
        notes=payload.notes,
        active=payload.active,
        created_by=actor,
    )
    db.add(equipment)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An equipment profile with this name already exists for the brewery",
        ) from exc

    await record_audit(
        db,
        action=AuditAction.EQUIPMENT_CREATED.value,
        entity_type="equipment_profile",
        entity_id=equipment.id,
        actor_id=actor,
        summary=f"Created equipment profile '{equipment.name}'",
        brewery_id=brewery_id,
        details={"system_type": equipment.system_type, "name": equipment.name},
    )
    await db.commit()
    await db.refresh(equipment)
    return equipment


async def update_equipment(
    db: AsyncSession, equipment_id: str, payload: EquipmentUpdate
) -> EquipmentProfile:
    equipment = await get_equipment(db, equipment_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return equipment

    before = {
        "name": equipment.name,
        "system_type": equipment.system_type,
        "target_batch_size": str(equipment.target_batch_size),
        "kettle_capacity": str(equipment.kettle_capacity),
        "active": equipment.active,
    }

    for key, value in data.items():
        setattr(equipment, key, _enum_value(value))

    actor = settings.default_actor_id
    equipment.updated_by = actor
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An equipment profile with this name already exists for the brewery",
        ) from exc

    await record_audit(
        db,
        action=AuditAction.EQUIPMENT_UPDATED.value,
        entity_type="equipment_profile",
        entity_id=equipment.id,
        actor_id=actor,
        summary=f"Updated equipment profile '{equipment.name}'",
        brewery_id=equipment.brewery_id,
        details={"before": before, "changes": {k: _enum_value(v) for k, v in data.items()}},
    )
    await db.commit()
    await db.refresh(equipment)
    return equipment
