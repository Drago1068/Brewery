"""Phase 4 durable fermentation timers and reminders.

Revision ID: 0007_phase4_timers_reminders
Revises: 0006_phase4_lifecycle_completion
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_phase4_timers_reminders"
down_revision: str | None = "0006_phase4_lifecycle_completion"
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
    op.create_table(
        "fermentation_timers",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage_instance_id", uuid, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", timestamp, nullable=False),
        sa.Column("planned_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("paused_at", timestamp),
        sa.Column("accumulated_pause_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", timestamp),
        sa.Column("clock_basis", sa.String(24), server_default="WALL_CLOCK", nullable=False),
        sa.Column("deadline_at", timestamp),
        sa.Column("expired_at", timestamp),
        sa.Column("acknowledged_at", timestamp),
        sa.Column("cancelled_at", timestamp),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("timer_type", sa.String(40), server_default="STAGE_PRIMARY", nullable=False),
        sa.Column("paused_by", sa.String(32)),
        sa.Column("continues_after_stage", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("replaces_timer_id", uuid, sa.ForeignKey("fermentation_timers.id",
            ondelete="SET NULL")),
        sa.Column("activation_ordinal", sa.Integer(), server_default="1", nullable=False),
        sa.Column("cancel_reason", sa.Text()),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-timer-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "fermentation_session_id", name="uq_fermentation_timer_session"),
        sa.ForeignKeyConstraint(
            ["stage_instance_id", "fermentation_session_id"],
            ["fermentation_stage_instances.id", "fermentation_stage_instances.fermentation_session_id"],  # noqa: E501
            name="fk_fermentation_timer_stage_session",
        ),
        sa.UniqueConstraint(
            "stage_instance_id",
            "name",
            "activation_ordinal",
            name="uq_fermentation_timer_stage_name_ordinal",
        ),
    )
    op.create_index(
        "ix_fermentation_timers_session_id",
        "fermentation_timers",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_timers_stage_instance_id",
        "fermentation_timers",
        ["stage_instance_id"],
    )

    op.create_table(
        "fermentation_timer_revisions",
        *common_columns(),
        sa.Column(
            "timer_id",
            uuid,
            sa.ForeignKey("fermentation_timers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("former_deadline_at", timestamp),
        sa.Column("former_duration_seconds", sa.Integer()),
        sa.Column("new_deadline_at", timestamp),
        sa.Column("new_duration_seconds", sa.Integer()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", uuid),
        sa.Column("operation_id", sa.String(64)),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fermentation_timer_revisions_timer_id",
        "fermentation_timer_revisions",
        ["timer_id"],
    )

    op.create_table(
        "fermentation_reminders",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage_instance_id", uuid, nullable=False),
        sa.Column("reminder_type", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("due_at", timestamp, nullable=False),
        sa.Column("acknowledged_at", timestamp),
        sa.Column("completed_at", timestamp),
        sa.Column("expired_at", timestamp),
        sa.Column("requirement_class", sa.String(64)),
        sa.Column("requirement_template_id", uuid),
        sa.Column("activation_ordinal", sa.Integer(), server_default="1", nullable=False),
        sa.Column("satisfaction_source_type", sa.String(40)),
        sa.Column("satisfaction_source_id", uuid),
        sa.Column("resolution_source_type", sa.String(40)),
        sa.Column("resolution_source_id", uuid),
        sa.Column("priority", sa.String(24), server_default="REQUIRED", nullable=False),
        sa.Column("skip_reason", sa.Text()),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-reminder-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "fermentation_session_id", name="uq_fermentation_reminder_session"),
        sa.ForeignKeyConstraint(
            ["stage_instance_id", "fermentation_session_id"],
            ["fermentation_stage_instances.id", "fermentation_stage_instances.fermentation_session_id"],  # noqa: E501
            name="fk_fermentation_reminder_stage_session",
        ),
        sa.UniqueConstraint(
            "fermentation_session_id",
            "reminder_type",
            "activation_ordinal",
            name="uq_fermentation_reminder_type_ordinal",
        ),
    )
    op.create_index(
        "ix_fermentation_reminders_session_id",
        "fermentation_reminders",
        ["fermentation_session_id"],
    )

    op.create_table(
        "fermentation_reminder_history",
        *common_columns(),
        sa.Column(
            "reminder_id",
            uuid,
            sa.ForeignKey("fermentation_reminders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prior_status", sa.String(24), nullable=False),
        sa.Column("new_status", sa.String(24), nullable=False),
        sa.Column("cause", sa.String(64), nullable=False),
        sa.Column("actor_user_id", uuid),
        sa.Column("operation_id", sa.String(64)),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fermentation_reminder_history_reminder_id",
        "fermentation_reminder_history",
        ["reminder_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fermentation_reminder_history_reminder_id",
        table_name="fermentation_reminder_history",
    )
    op.drop_table("fermentation_reminder_history")
    op.drop_index("ix_fermentation_reminders_session_id", table_name="fermentation_reminders")
    op.drop_table("fermentation_reminders")
    op.drop_index(
        "ix_fermentation_timer_revisions_timer_id",
        table_name="fermentation_timer_revisions",
    )
    op.drop_table("fermentation_timer_revisions")
    op.drop_index("ix_fermentation_timers_stage_instance_id", table_name="fermentation_timers")
    op.drop_index("ix_fermentation_timers_session_id", table_name="fermentation_timers")
    op.drop_table("fermentation_timers")
