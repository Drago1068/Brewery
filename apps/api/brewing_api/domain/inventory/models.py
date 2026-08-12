import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base


class InventoryLocation(UuidTimestampMixin, Base):
    __tablename__ = "inventory_locations"
    __table_args__ = (UniqueConstraint("owner_id", "name"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class InventoryTransaction(UuidTimestampMixin, Base):
    __tablename__ = "inventory_transactions"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    ingredient_lot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingredient_lots.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="RESTRICT"), index=True
    )
    destination_location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="RESTRICT"), index=True
    )
    transaction_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(80))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    note: Mapped[str | None] = mapped_column(Text)


class InventoryReservation(UuidTimestampMixin, Base):
    __tablename__ = "inventory_reservations"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    ingredient_lot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingredient_lots.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="RESTRICT"), index=True
    )
    recipe_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("recipe_versions.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SafetyStockPolicy(UuidTimestampMixin, Base):
    __tablename__ = "safety_stock_policies"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ingredients.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    threshold_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
