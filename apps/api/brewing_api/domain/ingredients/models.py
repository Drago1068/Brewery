import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base


class Ingredient(UuidTimestampMixin, Base):
    __tablename__ = "ingredients"
    __table_args__ = (UniqueConstraint("owner_id", "name"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(180))
    canonical_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class Supplier(UuidTimestampMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("owner_id", "name"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class SupplierItem(UuidTimestampMixin, Base):
    __tablename__ = "supplier_items"
    __table_args__ = (UniqueConstraint("supplier_id", "sku"),)

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("suppliers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sku: Mapped[str] = mapped_column(String(120), nullable=False)
    package_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    unit: Mapped[str | None] = mapped_column(String(16))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))


class IngredientLot(UuidTimestampMixin, Base):
    __tablename__ = "ingredient_lots"
    __table_args__ = (UniqueConstraint("owner_id", "lot_code"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("suppliers.id", ondelete="SET NULL"), index=True
    )
    lot_code: Mapped[str] = mapped_column(String(160), nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    best_by_date: Mapped[date | None] = mapped_column(Date)
    hop_alpha_acid_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    yeast_manufactured_date: Mapped[date | None] = mapped_column(Date)
    yeast_expiration_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
