import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base


class Measurement(UuidTimestampMixin, Base):
    __tablename__ = "measurements"

    brew_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    measurement_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    instrument: Mapped[str | None] = mapped_column(String(160))
    provenance: Mapped[str] = mapped_column(String(40), default="BREWER", nullable=False)
    correction_of_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("measurements.id", ondelete="RESTRICT"), index=True
    )


class Deviation(UuidTimestampMixin, Base):
    __tablename__ = "deviations"

    measurement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("measurements.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    target_value: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    actual_value: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    variance: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    tolerance: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="OPEN", nullable=False)

