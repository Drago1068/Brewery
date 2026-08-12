import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base


class BrewSession(UuidTimestampMixin, Base):
    __tablename__ = "brew_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    recipe_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipe_versions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), default="PLANNED", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_mash_temperature: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    mash_temperature_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    target_mash_ph: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    mash_ph_tolerance: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    target_mash_gravity: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    mash_gravity_tolerance: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    planned_mash_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)


class BrewStage(UuidTimestampMixin, Base):
    __tablename__ = "brew_stages"
    __table_args__ = (UniqueConstraint("brew_session_id", "name"),)

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="READY", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    target_temperature: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    temperature_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    target_ph: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    ph_tolerance: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    target_gravity: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    gravity_tolerance: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)


class BrewTimer(UuidTimestampMixin, Base):
    __tablename__ = "brew_timers"
    __table_args__ = (UniqueConstraint("brew_stage_id", "name"),)

    brew_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), default="Mash timer", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="RUNNING", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accumulated_pause_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

