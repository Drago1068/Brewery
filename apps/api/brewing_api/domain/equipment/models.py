import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base
from brewing_api.platform.time import utc_now


class EquipmentProfile(UuidTimestampMixin, Base):
    __tablename__ = "equipment_profiles"
    __table_args__ = (UniqueConstraint("owner_id", "name"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_batch_liters: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    preferred_volume_unit: Mapped[str] = mapped_column(String(16), default="L", nullable=False)
    preferred_temperature_unit: Mapped[str] = mapped_column(
        String(16), default="degC", nullable=False
    )
    brewhouse_efficiency: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    mash_efficiency: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    boil_off_liters_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    kettle_loss_liters: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0, nullable=False)
    mash_tun_deadspace_liters: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), default=0, nullable=False
    )
    fermenter_loss_liters: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), default=0, nullable=False
    )
    packaging_loss_liters: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), default=0, nullable=False
    )
    grain_absorption_liters_per_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0.8"), nullable=False
    )
    hop_absorption_liters_per_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("8.0"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
