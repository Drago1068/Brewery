import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid
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

