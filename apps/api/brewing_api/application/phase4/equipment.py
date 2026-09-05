from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from brewing_api.application.errors import NotFoundError
from brewing_api.domain.equipment.models import EquipmentProfile
from brewing_api.domain.identity.models import User
from brewing_api.domain.recipes.models import RecipeVersion


def _owned_equipment(
    db: Session, user: User, equipment_profile_id: uuid.UUID
) -> EquipmentProfile:
    equipment = db.get(EquipmentProfile, equipment_profile_id)
    if equipment is None or equipment.owner_id != user.id:
        raise NotFoundError("Equipment profile not found")
    return equipment


def calc_relevant_equipment_fields(equipment: EquipmentProfile) -> dict[str, Any]:
    """Copy calculation-relevant fields from the live Phase 2 equipment profile."""
    return {
        "name": equipment.name,
        "default_batch_liters": str(equipment.default_batch_liters),
        "brewhouse_efficiency": str(equipment.brewhouse_efficiency),
        "mash_efficiency": None
        if equipment.mash_efficiency is None
        else str(equipment.mash_efficiency),
        "boil_off_liters_per_hour": str(equipment.boil_off_liters_per_hour),
        "kettle_loss_liters": str(equipment.kettle_loss_liters),
        "mash_tun_deadspace_liters": str(equipment.mash_tun_deadspace_liters),
        "fermenter_loss_liters": str(equipment.fermenter_loss_liters),
        "packaging_loss_liters": str(equipment.packaging_loss_liters),
        "grain_absorption_liters_per_kg": str(equipment.grain_absorption_liters_per_kg),
        "hop_absorption_liters_per_kg": str(equipment.hop_absorption_liters_per_kg),
        "preferred_volume_unit": equipment.preferred_volume_unit,
        "preferred_temperature_unit": equipment.preferred_temperature_unit,
    }


def build_fermentation_equipment_snapshot(
    equipment: EquipmentProfile, *, snapshotted_at: datetime
) -> dict[str, Any]:
    """Immutable §29 fermentation equipment snapshot JSON."""
    payload = calc_relevant_equipment_fields(equipment)
    payload.update(
        {
            "source_equipment_profile_id": str(equipment.id),
            "snapshotted_at": snapshotted_at.isoformat(),
            "source_deleted": False,
            "fermenter_identity": "SPECIFIED",
        }
    )
    return payload


def resolve_start_equipment(
    db: Session,
    user: User,
    *,
    recipe_version: RecipeVersion,
    equipment_profile_id: uuid.UUID | None,
    snapshotted_at: datetime,
) -> tuple[uuid.UUID | None, dict[str, Any] | None]:
    """
    Resolve optional start-time fermenter equipment (§6.3 / §29).

    Priority: explicit start command ID, else RecipeVersion.equipment_profile_id.
    No profile → lawful absence (fermenter identity UNSPECIFIED).
    """
    selected_id = equipment_profile_id or recipe_version.equipment_profile_id
    if selected_id is None:
        return None, None
    equipment = _owned_equipment(db, user, selected_id)
    return equipment.id, build_fermentation_equipment_snapshot(
        equipment, snapshotted_at=snapshotted_at
    )
