import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base


class Measurement(UuidTimestampMixin, Base):
    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("id", "brew_session_id", name="uq_measurement_session"),
        UniqueConstraint("id", "brew_stage_id", name="uq_measurement_stage_session"),
        ForeignKeyConstraint(
            ["brew_stage_id", "brew_session_id"],
            ["brew_stages.id", "brew_stages.brew_session_id"],
            name="fk_measurement_stage_session",
        ),
        ForeignKeyConstraint(
            ["correction_of_id", "brew_session_id"],
            ["measurements.id", "measurements.brew_session_id"],
            name="fk_measurement_correction_session",
        ),
    )

    brew_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
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
    process_point: Mapped[str | None] = mapped_column(String(40))
    raw_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    raw_unit: Mapped[str | None] = mapped_column(String(16))
    canonical_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    canonical_unit: Mapped[str | None] = mapped_column(String(16))
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entry_method: Mapped[str | None] = mapped_column(String(32))
    method: Mapped[str | None] = mapped_column(String(32))
    sample_temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    temperature_compensated: Mapped[bool | None] = mapped_column(Boolean)
    vessel: Mapped[str | None] = mapped_column(String(40))
    conversion_model_id: Mapped[str | None] = mapped_column(String(80))
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    late_entry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    late_entry_reason: Mapped[str | None] = mapped_column(Text)
    available_at_original_stage_completion: Mapped[bool | None] = mapped_column(Boolean)
    available_at_original_session_completion: Mapped[bool | None] = mapped_column(Boolean)
    context: Mapped[dict | None] = mapped_column(JSON)
    definition_version: Mapped[str | None] = mapped_column(String(64))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)


class Deviation(UuidTimestampMixin, Base):
    __tablename__ = "deviations"

    measurement_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("measurements.id", ondelete="RESTRICT"), unique=True
    )
    brew_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True
    )
    brew_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True
    )
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    variance: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    tolerance: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    unit: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="OPEN", nullable=False)
    comparison_status: Mapped[str | None] = mapped_column(String(32))
    category: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    corrective_action: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[str | None] = mapped_column(String(80))
