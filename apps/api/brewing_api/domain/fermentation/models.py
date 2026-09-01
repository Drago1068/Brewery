import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
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
from brewing_api.domain.fermentation.constants import (
    ENTRY_SCHEMA_VERSION,
    PACKAGING_READINESS_SCHEMA_VERSION,
    PLAN_SCHEMA_VERSION,
    SESSION_STATE_SCHEMA_VERSION,
)
from brewing_api.platform.database import Base


class FermentationSession(UuidTimestampMixin, Base):
    __tablename__ = "fermentation_sessions"
    __table_args__ = (
        Index(
            "uq_fermentation_one_active_per_brew",
            "brew_session_id",
            unique=True,
            sqlite_where=text("status <> 'ABORTED'"),
            postgresql_where=text("status <> 'ABORTED'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    brew_pitch_handoff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_pitch_handoffs.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fermentation_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conditioning_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conditioning_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handoff_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aborted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    abort_reason: Mapped[str | None] = mapped_column(Text)
    conditioning_mode: Mapped[str | None] = mapped_column(String(32))
    plan_kind: Mapped[str | None] = mapped_column(String(32))
    materialization_rule_version: Mapped[str | None] = mapped_column(String(64))
    logical_plan_hash: Mapped[str | None] = mapped_column(String(64))
    plan_preview_hash: Mapped[str | None] = mapped_column(String(64))
    materialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_brew_revision: Mapped[int | None] = mapped_column(Integer)
    entry_schema_version: Mapped[str] = mapped_column(
        String(64), default=ENTRY_SCHEMA_VERSION, nullable=False
    )
    state_schema_version: Mapped[str] = mapped_column(
        String(64), default=SESSION_STATE_SCHEMA_VERSION, nullable=False
    )


class FermentationOperation(UuidTimestampMixin, Base):
    __tablename__ = "fermentation_operations"
    __table_args__ = (
        UniqueConstraint(
            "actor_user_id",
            "use_case",
            "aggregate_type",
            "aggregate_id",
            "operation_id",
            name="uq_phase4_operation_scope",
        ),
    )

    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    use_case: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(40), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    operation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    command_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    result_resource_type: Mapped[str | None] = mapped_column(String(40))
    result_resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tombstone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retained_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FermentationPlanSnapshot(UuidTimestampMixin, Base):
    __tablename__ = "fermentation_plan_snapshots"

    fermentation_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fermentation_sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(64), default=PLAN_SCHEMA_VERSION, nullable=False)
    plan_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    logical_plan_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class FermentationStageInstance(UuidTimestampMixin, Base):
    __tablename__ = "fermentation_stage_instances"
    __table_args__ = (
        UniqueConstraint(
            "fermentation_session_id",
            "canonical_stage_type",
            "occurrence_number",
            name="uq_fermentation_stage_occurrence",
        ),
    )

    fermentation_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fermentation_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    canonical_stage_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurrence_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    plan_step_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    requirement_set_fingerprint: Mapped[str | None] = mapped_column(String(64))


class FermentationOgConsumption(UuidTimestampMixin, Base):
    __tablename__ = "fermentation_og_consumptions"
    __table_args__ = (UniqueConstraint("fermentation_session_id"),)

    fermentation_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fermentation_sessions.id", ondelete="CASCADE"), nullable=False
    )
    brew_measurement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("measurements.id", ondelete="RESTRICT"), nullable=False
    )
    consumed_value: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    consumed_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(64), default="phase4-og-consumption-v1", nullable=False
    )
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FermentationYeastPitchReference(UuidTimestampMixin, Base):
    __tablename__ = "fermentation_yeast_pitch_references"
    __table_args__ = (UniqueConstraint("fermentation_session_id"),)

    fermentation_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fermentation_sessions.id", ondelete="CASCADE"), nullable=False
    )
    brew_pitch_handoff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_pitch_handoffs.id", ondelete="RESTRICT"), nullable=False
    )
    yeast_note: Mapped[str] = mapped_column(Text, nullable=False)
    pitch_temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    pitched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(64), default="phase4-yeast-pitch-reference-v1", nullable=False
    )


class FermentationJournalEvent(UuidTimestampMixin, Base):
    __tablename__ = "fermentation_journal_events"

    fermentation_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fermentation_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    fermentation_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fermentation_stage_instances.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(64), default="phase4-journal-v1", nullable=False
    )
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(64))


class PackagingReadinessHandoff(UuidTimestampMixin, Base):
    __tablename__ = "packaging_readiness_handoffs"
    __table_args__ = (UniqueConstraint("fermentation_session_id"),)

    fermentation_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fermentation_sessions.id", ondelete="CASCADE"), nullable=False
    )
    readiness_status: Mapped[str] = mapped_column(String(32), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(64), default=PACKAGING_READINESS_SCHEMA_VERSION, nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
