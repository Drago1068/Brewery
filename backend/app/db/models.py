from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AppMeta(Base):
    """Foundation metadata row used to verify migrations and persistence."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Brewery(Base):
    __tablename__ = "breweries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    preferred_units: Mapped[str] = mapped_column(String(16), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    default_batch_size: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    default_batch_size_unit: Mapped[str] = mapped_column(String(8), nullable=False)
    default_brewhouse_efficiency: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    equipment_profiles: Mapped[list["EquipmentProfile"]] = relationship(
        back_populates="brewery", cascade="all, delete-orphan"
    )
    ingredients: Mapped[list["Ingredient"]] = relationship(
        back_populates="brewery", cascade="all, delete-orphan"
    )
    recipes: Mapped[list["Recipe"]] = relationship(
        back_populates="brewery", cascade="all, delete-orphan"
    )


class EquipmentProfile(Base):
    __tablename__ = "equipment_profiles"
    __table_args__ = (
        UniqueConstraint("brewery_id", "name", name="uq_equipment_brewery_name"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    brewery_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("breweries.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    system_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_batch_size: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    target_batch_size_unit: Mapped[str] = mapped_column(String(8), nullable=False)
    kettle_capacity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    kettle_capacity_unit: Mapped[str] = mapped_column(String(8), nullable=False)
    mash_capacity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    mash_capacity_unit: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    boil_off_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    boil_off_rate_unit: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    trub_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    trub_loss_unit: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    fermenter_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    fermenter_loss_unit: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    typical_brewhouse_efficiency: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    brewery: Mapped["Brewery"] = relationship(back_populates="equipment_profiles")


class AuditEvent(Base):
    """Lightweight append-oriented audit foundation for Epic 1."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    brewery_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("breweries.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Ingredient(Base):
    """Reusable ingredient definition (library), brewery-owned in Epic 1."""

    __tablename__ = "ingredients"
    __table_args__ = (
        UniqueConstraint("brewery_id", "category", "name", name="uq_ingredient_identity"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    brewery_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("breweries.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    brewery: Mapped["Brewery"] = relationship(back_populates="ingredients")
    fermentable_profile: Mapped[Optional["FermentableProfile"]] = relationship(
        back_populates="ingredient", uselist=False, cascade="all, delete-orphan"
    )
    hop_profile: Mapped[Optional["HopProfile"]] = relationship(
        back_populates="ingredient", uselist=False, cascade="all, delete-orphan"
    )
    yeast_profile: Mapped[Optional["YeastProfile"]] = relationship(
        back_populates="ingredient", uselist=False, cascade="all, delete-orphan"
    )
    lots: Mapped[list["IngredientLot"]] = relationship(
        back_populates="ingredient", cascade="all, delete-orphan"
    )


class FermentableProfile(Base):
    __tablename__ = "fermentable_profiles"

    ingredient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    fermentable_type: Mapped[str] = mapped_column(String(32), nullable=False)
    color_lovibond: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)
    potential_sg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    yield_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)

    ingredient: Mapped["Ingredient"] = relationship(back_populates="fermentable_profile")


class HopProfile(Base):
    __tablename__ = "hop_profiles"

    ingredient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hop_type: Mapped[str] = mapped_column(String(32), nullable=False)
    default_alpha_acid: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    beta_acid: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    aroma_descriptors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ingredient: Mapped["Ingredient"] = relationship(back_populates="hop_profile")


class YeastProfile(Base):
    __tablename__ = "yeast_profiles"

    ingredient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    yeast_type: Mapped[str] = mapped_column(String(32), nullable=False)
    strain: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    attenuation_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    attenuation_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    temperature_min_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    temperature_max_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)

    ingredient: Mapped["Ingredient"] = relationship(back_populates="yeast_profile")


class IngredientLot(Base):
    __tablename__ = "ingredient_lots"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    brewery_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("breweries.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False
    )
    supplier: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    supplier_lot_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    manufacturer_lot_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    received_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiration_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    purchase_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    storage_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Lot-specific hop alpha may differ from library default.
    actual_alpha_acid: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantity_reserved: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0")
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    ingredient: Mapped["Ingredient"] = relationship(back_populates="lots")
    transactions: Mapped[list["InventoryTransaction"]] = relationship(
        back_populates="lot", cascade="all, delete-orphan"
    )


class InventoryTransaction(Base):
    """Append-oriented inventory movement. History is authoritative."""

    __tablename__ = "inventory_transactions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    brewery_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("breweries.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_lot_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ingredient_lots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lot: Mapped["IngredientLot"] = relationship(back_populates="transactions")


class Recipe(Base):
    """Conceptual beer identity. Formulation lives on RecipeVersion."""

    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    brewery_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("breweries.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    style: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    current_version_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    brewery: Mapped["Brewery"] = relationship(back_populates="recipes")
    versions: Mapped[list["RecipeVersion"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        foreign_keys="RecipeVersion.recipe_id",
    )


class RecipeVersion(Base):
    __tablename__ = "recipe_versions"
    __table_args__ = (
        UniqueConstraint("recipe_id", "version_number", name="uq_recipe_version_number"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    recipe_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    parent_version_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipe_versions.id", ondelete="SET NULL"), nullable=True
    )
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    batch_size: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    batch_size_unit: Mapped[str] = mapped_column(String(8), nullable=False)
    equipment_profile_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("equipment_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    brewhouse_efficiency: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    boil_time_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)
    mash_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    recipe: Mapped["Recipe"] = relationship(
        back_populates="versions", foreign_keys=[recipe_id]
    )
    intent: Mapped[Optional["RecipeIntent"]] = relationship(
        back_populates="recipe_version", uselist=False, cascade="all, delete-orphan"
    )
    fermentables: Mapped[list["RecipeVersionFermentable"]] = relationship(
        back_populates="recipe_version", cascade="all, delete-orphan"
    )
    hops: Mapped[list["RecipeVersionHop"]] = relationship(
        back_populates="recipe_version", cascade="all, delete-orphan"
    )
    yeasts: Mapped[list["RecipeVersionYeast"]] = relationship(
        back_populates="recipe_version", cascade="all, delete-orphan"
    )
    adjuncts: Mapped[list["RecipeVersionAdjunct"]] = relationship(
        back_populates="recipe_version", cascade="all, delete-orphan"
    )
    water_additions: Mapped[list["RecipeVersionWaterAddition"]] = relationship(
        back_populates="recipe_version", cascade="all, delete-orphan"
    )
    mash_steps: Mapped[list["RecipeVersionMashStep"]] = relationship(
        back_populates="recipe_version", cascade="all, delete-orphan"
    )
    targets: Mapped[list["RecipeVersionTarget"]] = relationship(
        back_populates="recipe_version", cascade="all, delete-orphan"
    )


class RecipeIntent(Base):
    """Lightweight sensory/formulation intent bound to a RecipeVersion."""

    __tablename__ = "recipe_intents"

    recipe_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("recipe_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    desired_aroma: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    desired_flavor: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    desired_bitterness: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    desired_sweetness_dryness: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    desired_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    desired_carbonation_impression: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overall_objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    recipe_version: Mapped["RecipeVersion"] = relationship(back_populates="intent")


class RecipeVersionFermentable(Base):
    __tablename__ = "recipe_version_fermentables"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    recipe_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    ingredient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    color_lovibond: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)
    potential_sg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    yield_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    recipe_version: Mapped["RecipeVersion"] = relationship(back_populates="fermentables")


class RecipeVersionHop(Base):
    __tablename__ = "recipe_version_hops"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    recipe_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    ingredient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    alpha_acid: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    time_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    recipe_version: Mapped["RecipeVersion"] = relationship(back_populates="hops")


class RecipeVersionYeast(Base):
    __tablename__ = "recipe_version_yeasts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    recipe_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    ingredient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    expected_attenuation: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    temperature_min_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    temperature_max_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    recipe_version: Mapped["RecipeVersion"] = relationship(back_populates="yeasts")


class RecipeVersionAdjunct(Base):
    __tablename__ = "recipe_version_adjuncts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    recipe_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    ingredient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    recipe_version: Mapped["RecipeVersion"] = relationship(back_populates="adjuncts")


class RecipeVersionWaterAddition(Base):
    __tablename__ = "recipe_version_water_additions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    recipe_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    recipe_version: Mapped["RecipeVersion"] = relationship(back_populates="water_additions")


class RecipeVersionMashStep(Base):
    __tablename__ = "recipe_version_mash_steps"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    recipe_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Infusion")
    target_temperature_c: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)
    mash_water_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    mash_water_unit: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    sparge_water_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    sparge_water_unit: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    recipe_version: Mapped["RecipeVersion"] = relationship(back_populates="mash_steps")


class RecipeVersionTarget(Base):
    __tablename__ = "recipe_version_targets"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    recipe_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recipe_version: Mapped["RecipeVersion"] = relationship(back_populates="targets")
