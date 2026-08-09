from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Brewery
from app.domain.enums import AuditAction
from app.schemas.brewery import BreweryCreate, BreweryUpdate
from app.services.audit import record_audit


async def get_primary_brewery(db: AsyncSession) -> Brewery | None:
    result = await db.execute(select(Brewery).order_by(Brewery.created_at.asc()).limit(1))
    return result.scalar_one_or_none()


async def get_brewery(db: AsyncSession, brewery_id: str) -> Brewery:
    brewery = await db.get(Brewery, brewery_id)
    if brewery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brewery not found")
    return brewery


async def create_brewery(db: AsyncSession, payload: BreweryCreate) -> Brewery:
    existing = await get_primary_brewery(db)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A brewery already exists. Update the existing brewery instead.",
        )

    actor = settings.default_actor_id
    brewery = Brewery(
        name=payload.name,
        preferred_units=payload.preferred_units.value,
        timezone=payload.timezone,
        default_batch_size=payload.default_batch_size,
        default_batch_size_unit=payload.default_batch_size_unit.value,
        default_brewhouse_efficiency=payload.default_brewhouse_efficiency,
        created_by=actor,
    )
    db.add(brewery)
    await db.flush()
    await record_audit(
        db,
        action=AuditAction.BREWERY_CREATED.value,
        entity_type="brewery",
        entity_id=brewery.id,
        actor_id=actor,
        summary=f"Created brewery '{brewery.name}'",
        brewery_id=brewery.id,
        details={"name": brewery.name, "preferred_units": brewery.preferred_units},
    )
    await db.commit()
    await db.refresh(brewery)
    return brewery


async def update_brewery(db: AsyncSession, brewery_id: str, payload: BreweryUpdate) -> Brewery:
    brewery = await get_brewery(db, brewery_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return brewery

    preferred = data.get("preferred_units", brewery.preferred_units)
    preferred_value = preferred.value if hasattr(preferred, "value") else preferred
    unit = data.get("default_batch_size_unit", brewery.default_batch_size_unit)
    unit_value = unit.value if hasattr(unit, "value") else unit

    if preferred_value == "US" and unit_value != "gal":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="US preferred units require default_batch_size_unit=gal",
        )
    if preferred_value == "METRIC" and unit_value != "L":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="METRIC preferred units require default_batch_size_unit=L",
        )

    before = {
        "name": brewery.name,
        "preferred_units": brewery.preferred_units,
        "timezone": brewery.timezone,
        "default_batch_size": str(brewery.default_batch_size),
        "default_batch_size_unit": brewery.default_batch_size_unit,
        "default_brewhouse_efficiency": str(brewery.default_brewhouse_efficiency),
    }

    for key, value in data.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(brewery, key, value)

    actor = settings.default_actor_id
    brewery.updated_by = actor
    await record_audit(
        db,
        action=AuditAction.BREWERY_UPDATED.value,
        entity_type="brewery",
        entity_id=brewery.id,
        actor_id=actor,
        summary=f"Updated brewery '{brewery.name}'",
        brewery_id=brewery.id,
        details={"before": before, "after": data},
    )
    await db.commit()
    await db.refresh(brewery)
    return brewery
