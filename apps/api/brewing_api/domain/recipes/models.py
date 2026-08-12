import uuid
from decimal import Decimal

from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base


class Recipe(UuidTimestampMixin, Base):
    __tablename__ = "recipes"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class RecipeVersion(UuidTimestampMixin, Base):
    __tablename__ = "recipe_versions"
    __table_args__ = (UniqueConstraint("recipe_id", "version_number"),)

    recipe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    target_mash_temperature: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    mash_temperature_unit: Mapped[str] = mapped_column(String(16), default="degF", nullable=False)
    target_mash_ph: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    mash_ph_tolerance: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    target_mash_gravity: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    mash_gravity_tolerance: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    planned_mash_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    equipment_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("equipment_profiles.id", ondelete="RESTRICT"), index=True
    )
    style_name: Mapped[str | None] = mapped_column(String(160))
    bjcp_category: Mapped[str | None] = mapped_column(String(80))
    batch_size_liters: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    target_og: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    target_fg: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    target_abv_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    target_ibu: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    target_color_srm: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    target_carbonation_volumes: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    boil_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    apparent_attenuation: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    equipment_snapshot: Mapped[dict | None] = mapped_column(JSON)
    calculation_inputs: Mapped[dict | None] = mapped_column(JSON)
    calculation_outputs: Mapped[dict | None] = mapped_column(JSON)
    model_versions: Mapped[dict | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)


class RecipeIngredient(UuidTimestampMixin, Base):
    __tablename__ = "recipe_ingredients"

    recipe_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipe_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    ingredient_lot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingredient_lots.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    use_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    timing_minutes: Mapped[int | None] = mapped_column(Integer)
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    notes: Mapped[str | None] = mapped_column(Text)


class RecipeProcessStep(UuidTimestampMixin, Base):
    __tablename__ = "recipe_process_steps"

    recipe_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipe_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step_type: Mapped[str] = mapped_column(String(40), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WaterProfileTarget(UuidTimestampMixin, Base):
    __tablename__ = "water_profile_targets"

    recipe_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipe_versions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    calcium_ppm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    magnesium_ppm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    sodium_ppm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    chloride_ppm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    sulfate_ppm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    bicarbonate_ppm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))


class IngredientSubstitution(UuidTimestampMixin, Base):
    __tablename__ = "ingredient_substitutions"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    original_ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    substitute_ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    conversion_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 5), default=1, nullable=False)
    process_impact: Mapped[str] = mapped_column(Text, nullable=False)
    flavor_impact: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    requires_brewer_approval: Mapped[bool] = mapped_column(default=True, nullable=False)
