import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base


class BrewSession(UuidTimestampMixin, Base):
    __tablename__ = "brew_sessions"
    __table_args__ = (
        Index(
            "uq_brew_sessions_one_active_or_paused",
            "user_id",
            unique=True,
            sqlite_where=text("status IN ('ACTIVE','PAUSED')"),
            postgresql_where=text("status IN ('ACTIVE','PAUSED')"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    recipe_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recipe_versions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), default="PLANNED", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aborted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    abort_reason: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    plan_kind: Mapped[str | None] = mapped_column(String(32))
    materialization_rule_version: Mapped[str | None] = mapped_column(String(64))
    logical_plan_hash: Mapped[str | None] = mapped_column(String(64))
    plan_preview_hash: Mapped[str | None] = mapped_column(String(64))
    materialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_mash_temperature: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    mash_temperature_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    target_mash_ph: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    mash_ph_tolerance: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    target_mash_gravity: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    mash_gravity_tolerance: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    planned_mash_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)


class BrewStage(UuidTimestampMixin, Base):
    __tablename__ = "brew_stages"
    __table_args__ = (
        UniqueConstraint(
            "brew_session_id", "plan_step_id", "occurrence_number", name="uq_stage_occurrence"
        ),
    )

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    target_temperature: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    temperature_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    target_ph: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    ph_tolerance: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    target_gravity: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    gravity_tolerance: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    plan_step_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    canonical_stage_type: Mapped[str | None] = mapped_column(String(40))
    occurrence_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    runtime_occurrence_kind: Mapped[str | None] = mapped_column(String(24))
    runtime_source_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="SET NULL")
    )
    runtime_reason: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(Text)
    requirement_set_fingerprint: Mapped[str | None] = mapped_column(String(64))
    active_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    wall_clock_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    accumulated_pause_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class BrewTimer(UuidTimestampMixin, Base):
    __tablename__ = "brew_timers"
    __table_args__ = (UniqueConstraint("brew_stage_id", "name"),)

    brew_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    brew_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80), default="Mash timer", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="RUNNING", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accumulated_pause_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clock_basis: Mapped[str] = mapped_column(String(24), default="WALL_CLOCK", nullable=False)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    timer_type: Mapped[str] = mapped_column(String(40), default="STAGE_PRIMARY", nullable=False)
    paused_by: Mapped[str | None] = mapped_column(String(32))
    continues_after_stage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    replaces_timer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brew_timers.id", ondelete="SET NULL")
    )
    addition_requirement_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
