"""Helpers for Phase 4 yeast provenance tests."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from brewing_api.domain.brew_day.models import BrewPitchHandoff
from brewing_api.domain.brew_sessions.models import BrewSession
from brewing_api.domain.fermentation.models import (
    FermentationSession,
    FermentationYeastPitchReference,
)
from brewing_api.domain.identity.models import User
from brewing_api.domain.ingredients.models import Ingredient, IngredientLot
from brewing_api.domain.recipes.models import Recipe, RecipeVersion
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now


def _brewer_user(db) -> User:
    user = db.scalar(select(User).where(User.username == "brewer"))
    assert user is not None
    return user


def create_ingredient_lot(
    *,
    owner_id: uuid.UUID | None = None,
    manufacturer: str = "Wyeast Labs",
    strain: str = "1056 American Ale",
    generation_label: str = "Generation 1",
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create an ingredient + ingredient lot directly. Returns (lot_id, ingredient_id)."""
    with SessionLocal() as db:
        owner = _brewer_user(db).id if owner_id is None else owner_id
        ingredient = Ingredient(
            owner_id=owner,
            name=strain,
            category="YEAST",
            manufacturer=manufacturer,
            canonical_unit="each",
            attributes={
                "strain": strain,
                "generation_label": generation_label,
            },
        )
        db.add(ingredient)
        db.flush()
        lot = IngredientLot(
            owner_id=owner,
            ingredient_id=ingredient.id,
            lot_code=f"LOT-{uuid.uuid4().hex[:8]}",
            received_quantity=Decimal("1.0000"),
            unit="each",
        )
        db.add(lot)
        db.commit()
        return lot.id, ingredient.id


def create_source_fermentation_session(
    *,
    owner_id: uuid.UUID | None = None,
    status: str = "CONDITIONING_COMPLETE",
    pitched_at_offset: timedelta = timedelta(hours=2),
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a full fermentation session + yeast reference chain directly.

    Returns (fermentation_session_id, yeast_reference_id).
    """
    with SessionLocal() as db:
        owner = _brewer_user(db) if owner_id is None else db.get(User, owner_id)
        assert owner is not None
        now = utc_now()

        recipe = Recipe(owner_id=owner.id, name=f"Source Ale {uuid.uuid4().hex[:6]}")
        db.add(recipe)
        db.flush()
        version = RecipeVersion(
            recipe_id=recipe.id,
            version_number=1,
            target_mash_temperature=Decimal("152.00"),
            mash_temperature_unit="degF",
            target_mash_ph=Decimal("5.30"),
            mash_ph_tolerance=Decimal("0.05"),
            target_mash_gravity=Decimal("1.050"),
            mash_gravity_tolerance=Decimal("0.003"),
            planned_mash_duration_minutes=60,
        )
        db.add(version)
        db.flush()

        brew = BrewSession(
            user_id=owner.id,
            recipe_version_id=version.id,
            status="COMPLETED",
            target_mash_temperature=Decimal("152.00"),
            mash_temperature_unit="degF",
            target_mash_ph=Decimal("5.30"),
            mash_ph_tolerance=Decimal("0.05"),
            target_mash_gravity=Decimal("1.050"),
            mash_gravity_tolerance=Decimal("0.003"),
            planned_mash_duration_minutes=60,
        )
        db.add(brew)
        db.flush()

        handoff = BrewPitchHandoff(
            brew_session_id=brew.id,
            pitched_at=now - pitched_at_offset,
            pitch_temperature_c=Decimal("18.0"),
            yeast_addition_note="Source yeast",
            actor_user_id=owner.id,
        )
        db.add(handoff)
        db.flush()

        session = FermentationSession(
            user_id=owner.id,
            brew_session_id=brew.id,
            brew_pitch_handoff_id=handoff.id,
            status=status,
            revision=1,
            started_at=now - pitched_at_offset,
        )
        db.add(session)
        db.flush()

        reference = FermentationYeastPitchReference(
            fermentation_session_id=session.id,
            brew_pitch_handoff_id=handoff.id,
            yeast_note="Source yeast",
            pitch_temperature_c=Decimal("18.0"),
            pitched_at=now - pitched_at_offset,
        )
        db.add(reference)
        db.commit()
        return session.id, reference.id


def fermentation_user_id() -> uuid.UUID:
    with SessionLocal() as db:
        return _brewer_user(db).id
