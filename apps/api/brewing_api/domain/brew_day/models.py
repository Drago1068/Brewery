import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
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


class BrewPlanStep(UuidTimestampMixin, Base):
    __tablename__ = "brew_plan_steps"
    __table_args__ = (UniqueConstraint("brew_session_id", "plan_step_id"),)

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plan_step_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    canonical_stage_type: Mapped[str] = mapped_column(String(40), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_process_step_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    stable_source_discriminator: Mapped[str] = mapped_column(String(80), nullable=False)
    expansion_rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    planned_same_type_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    predecessor_plan_step_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    planned_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    clock_basis: Mapped[str] = mapped_column(String(24), default="WALL_CLOCK", nullable=False)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class BrewRequirementTemplate(UuidTimestampMixin, Base):
    __tablename__ = "brew_requirement_templates"
    __table_args__ = (UniqueConstraint("brew_session_id", "requirement_template_id"),)

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plan_step_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    requirement_template_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    requirement_class: Mapped[str] = mapped_column(String(32), nullable=False)
    definition_key: Mapped[str] = mapped_column(String(80), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    waivable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    runtime_occurrence_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    addition_repeat_policy: Mapped[str | None] = mapped_column(String(32))
    addition_repeat_policy_version: Mapped[str | None] = mapped_column(String(64))
    assignment_provenance: Mapped[str | None] = mapped_column(String(40))
    source_addition_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    policy_fingerprint: Mapped[str | None] = mapped_column(String(64))


class BrewStageRequirement(UuidTimestampMixin, Base):
    __tablename__ = "brew_stage_requirements"
    __table_args__ = (
        UniqueConstraint(
            "stage_instance_id",
            "requirement_template_id",
            "requirement_class",
            name="uq_stage_requirement_template",
        ),
    )

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requirement_template_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    requirement_class: Mapped[str] = mapped_column(String(32), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    waivable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    provenance: Mapped[str] = mapped_column(String(40), default="PLANNED", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    satisfaction_source_type: Mapped[str | None] = mapped_column(String(40))
    satisfaction_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class BrewAdditionEvent(UuidTimestampMixin, Base):
    __tablename__ = "brew_addition_events"

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    planned_addition_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    source_addition_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    execution_status: Mapped[str] = mapped_column(String(24), nullable=False)
    planned_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    planned_unit: Mapped[str | None] = mapped_column(String(16))
    actual_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    actual_unit: Mapped[str | None] = mapped_column(String(16))
    actual_executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timing_basis: Mapped[str | None] = mapped_column(String(32))
    timing_offset_seconds: Mapped[int | None] = mapped_column(Integer)
    signed_variance_seconds: Mapped[int | None] = mapped_column(Integer)
    actual_ingredient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actual_lot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    substitution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    note: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    late_entry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    late_entry_reason: Mapped[str | None] = mapped_column(Text)
    available_at_original_stage_completion: Mapped[bool | None] = mapped_column(Boolean)
    available_at_original_session_completion: Mapped[bool | None] = mapped_column(Boolean)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BrewAdditionCorrection(UuidTimestampMixin, Base):
    __tablename__ = "brew_addition_corrections"
    __table_args__ = (UniqueConstraint("correction_of_id"),)

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    original_addition_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_addition_events.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    correction_of_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    execution_status: Mapped[str] = mapped_column(String(24), nullable=False)
    actual_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    actual_unit: Mapped[str | None] = mapped_column(String(16))
    actual_executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_ingredient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actual_lot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    substitution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    note: Mapped[str | None] = mapped_column(Text)
    changed_fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    rule_version: Mapped[str] = mapped_column(String(64), default="phase3-addition-correction-v1")
    late_entry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BrewTimerRevision(UuidTimestampMixin, Base):
    __tablename__ = "brew_timer_revisions"

    timer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_timers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    former_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    former_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    new_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    operation_id: Mapped[str | None] = mapped_column(String(64))


class BrewWaiver(UuidTimestampMixin, Base):
    __tablename__ = "brew_waivers"

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    requirement_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    operation_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    superseded_by_type: Mapped[str | None] = mapped_column(String(40))


class BrewNote(UuidTimestampMixin, Base):
    __tablename__ = "brew_notes"

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stage_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    correction_of_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brew_notes.id", ondelete="RESTRICT")
    )
    post_terminal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BrewAttachment(UuidTimestampMixin, Base):
    __tablename__ = "brew_attachments"

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stage_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_length: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    caption: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(24), default="FINAL", nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str | None] = mapped_column(Text)


class BrewOperation(UuidTimestampMixin, Base):
    __tablename__ = "brew_operations"
    __table_args__ = (
        UniqueConstraint(
            "actor_user_id",
            "use_case",
            "aggregate_type",
            "aggregate_id",
            "operation_id",
            name="uq_phase3_operation_scope",
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


class BrewPitchHandoff(UuidTimestampMixin, Base):
    __tablename__ = "brew_pitch_handoffs"
    __table_args__ = (UniqueConstraint("brew_session_id"),)

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), nullable=False
    )
    pitched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pitch_temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    yeast_addition_note: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), default="phase3-pitch-handoff-v1")


class BrewReminderHistory(UuidTimestampMixin, Base):
    __tablename__ = "brew_reminder_history"

    reminder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("notifications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    prior_status: Mapped[str] = mapped_column(String(24), nullable=False)
    new_status: Mapped[str] = mapped_column(String(24), nullable=False)
    cause: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    operation_id: Mapped[str | None] = mapped_column(String(64))
