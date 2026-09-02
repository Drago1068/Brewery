"""Phase 4 fermentation, conditioning, and yeast persistence.

Revision ID: 0004_phase4_fermentation_conditioning_yeast
Revises: 0003_phase3_brew_day_os
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_phase4_fermentation_conditioning_yeast"
down_revision: str | None = "0003_phase3_brew_day_os"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid = sa.Uuid()
timestamp = sa.DateTime(timezone=True)


def common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", uuid, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
    ]


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
    op.create_table(
        "fermentation_sessions",
        *common_columns(),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "brew_session_id",
            uuid,
            sa.ForeignKey("brew_sessions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "brew_pitch_handoff_id",
            uuid,
            sa.ForeignKey("brew_pitch_handoffs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("started_at", timestamp),
        sa.Column("paused_at", timestamp),
        sa.Column("fermentation_completed_at", timestamp),
        sa.Column("conditioning_started_at", timestamp),
        sa.Column("conditioning_completed_at", timestamp),
        sa.Column("completion_assessed_at", timestamp),
        sa.Column("handoff_ready_at", timestamp),
        sa.Column("closed_at", timestamp),
        sa.Column("aborted_at", timestamp),
        sa.Column("abort_reason", sa.Text()),
        sa.Column("conditioning_mode", sa.String(32)),
        sa.Column("plan_kind", sa.String(32)),
        sa.Column("materialization_rule_version", sa.String(64)),
        sa.Column("logical_plan_hash", sa.String(64)),
        sa.Column("plan_preview_hash", sa.String(64)),
        sa.Column("materialized_at", timestamp),
        sa.Column("expected_brew_revision", sa.Integer()),
        sa.Column(
            "entry_schema_version",
            sa.String(64),
            server_default="phase4-entry-v1",
            nullable=False,
        ),
        sa.Column(
            "state_schema_version",
            sa.String(64),
            server_default="phase4-session-state-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fermentation_sessions_user_id", "fermentation_sessions", ["user_id"])
    op.create_index(
        "ix_fermentation_sessions_brew_session_id", "fermentation_sessions", ["brew_session_id"]
    )
    op.create_index(
        "uq_fermentation_one_active_per_brew",
        "fermentation_sessions",
        ["brew_session_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'ABORTED'"),
        sqlite_where=sa.text("status <> 'ABORTED'"),
    )

    op.create_table(
        "fermentation_operations",
        *common_columns(),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("use_case", sa.String(80), nullable=False),
        sa.Column("aggregate_type", sa.String(40), nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("command_schema_version", sa.String(64), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("result_resource_type", sa.String(40)),
        sa.Column("result_resource_id", uuid),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("tombstone", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("completed_at", timestamp),
        sa.Column("retained_until", timestamp),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_user_id",
            "use_case",
            "aggregate_type",
            "aggregate_id",
            "operation_id",
            name="uq_phase4_operation_scope",
        ),
    )
    op.create_index(
        "ix_fermentation_operations_actor_user_id", "fermentation_operations", ["actor_user_id"]
    )

    op.create_table(
        "fermentation_plan_snapshots",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "schema_version", sa.String(64), server_default="phase4-plan-v1", nullable=False
        ),
        sa.Column("plan_kind", sa.String(32), nullable=False),
        sa.Column("logical_plan_hash", sa.String(64), nullable=False),
        sa.Column("preview_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fermentation_session_id"),
    )

    op.create_table(
        "fermentation_stage_instances",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("canonical_stage_type", sa.String(40), nullable=False),
        sa.Column("occurrence_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", timestamp),
        sa.Column("completed_at", timestamp),
        sa.Column("paused_at", timestamp),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("plan_step_id", uuid),
        sa.Column("requirement_set_fingerprint", sa.String(64)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fermentation_session_id",
            "canonical_stage_type",
            "occurrence_number",
            name="uq_fermentation_stage_occurrence",
        ),
    )
    op.create_index(
        "ix_fermentation_stage_instances_fermentation_session_id",
        "fermentation_stage_instances",
        ["fermentation_session_id"],
    )

    op.create_table(
        "fermentation_og_consumptions",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brew_measurement_id",
            uuid,
            sa.ForeignKey("measurements.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("consumed_value", sa.Numeric(8, 3), nullable=False),
        sa.Column("consumed_unit", sa.String(16), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-og-consumption-v1",
            nullable=False,
        ),
        sa.Column("consumed_at", timestamp, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fermentation_session_id"),
    )

    op.create_table(
        "fermentation_yeast_pitch_references",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brew_pitch_handoff_id",
            uuid,
            sa.ForeignKey("brew_pitch_handoffs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("yeast_note", sa.Text(), nullable=False),
        sa.Column("pitch_temperature_c", sa.Numeric(6, 2)),
        sa.Column("pitched_at", timestamp, nullable=False),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-yeast-pitch-reference-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fermentation_session_id"),
    )

    op.create_table(
        "fermentation_journal_events",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fermentation_stage_id",
            uuid,
            sa.ForeignKey("fermentation_stage_instances.id", ondelete="CASCADE"),
        ),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=False),
        sa.Column(
            "schema_version", sa.String(64), server_default="phase4-journal-v1", nullable=False
        ),
        sa.Column("occurred_at", timestamp),
        sa.Column("recorded_at", timestamp),
        sa.Column("actor_user_id", uuid),
        sa.Column("operation_id", sa.String(64)),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("causation_id", sa.String(64)),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fermentation_journal_events_fermentation_session_id",
        "fermentation_journal_events",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_journal_events_event_type", "fermentation_journal_events", ["event_type"]
    )

    op.create_table(
        "packaging_readiness_handoffs",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("readiness_status", sa.String(32), nullable=False),
        sa.Column("assessed_at", timestamp, nullable=False),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-packaging-readiness-v1",
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fermentation_session_id"),
    )


def downgrade() -> None:
    op.drop_table("packaging_readiness_handoffs")
    op.drop_table("fermentation_journal_events")
    op.drop_table("fermentation_yeast_pitch_references")
    op.drop_table("fermentation_og_consumptions")
    op.drop_table("fermentation_stage_instances")
    op.drop_table("fermentation_plan_snapshots")
    op.drop_table("fermentation_operations")
    op.drop_index("uq_fermentation_one_active_per_brew", table_name="fermentation_sessions")
    op.drop_table("fermentation_sessions")
