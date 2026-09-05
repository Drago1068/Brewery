"""Phase 4 fermentation actions and post-pitch additions (P4-FR-052–057/061/070).

Revision ID: 0014_phase4_actions_additions
Revises: 0013_phase4_waivers
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_phase4_actions_additions"
down_revision: str | None = "0013_phase4_waivers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid = sa.Uuid()
timestamp = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "fermentation_actions",
        sa.Column("id", uuid, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_instance_id",
            uuid,
            sa.ForeignKey("fermentation_stage_instances.id", ondelete="SET NULL"),
        ),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("occurred_at", timestamp, nullable=False),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("planned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.Column("late_entry", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-action-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fermentation_actions_fermentation_session_id",
        "fermentation_actions",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_actions_stage_instance_id",
        "fermentation_actions",
        ["stage_instance_id"],
    )
    op.create_index("ix_fermentation_actions_actor_user_id", "fermentation_actions", ["actor_user_id"])
    op.create_index("ix_fermentation_actions_operation_id", "fermentation_actions", ["operation_id"])

    op.create_table(
        "fermentation_addition_requirements",
        sa.Column("id", uuid, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_instance_id",
            uuid,
            sa.ForeignKey("fermentation_stage_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requirement_id", uuid, nullable=False),
        sa.Column("requirement_template_id", uuid, nullable=False),
        sa.Column("requirement_class", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("waivable", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("source_recipe_ingredient_id", uuid, nullable=False),
        sa.Column("ingredient_id", uuid, nullable=False),
        sa.Column("ingredient_lot_id", uuid),
        sa.Column("planned_amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("planned_unit", sa.String(16), nullable=False),
        sa.Column("use_stage", sa.String(40), nullable=False),
        sa.Column("timing_basis", sa.String(32), nullable=False),
        sa.Column("timing_offset_seconds", sa.Integer(), nullable=False),
        sa.Column("planned_due_at", timestamp, nullable=False),
        sa.Column("runtime_occurrence_policy", sa.String(32), nullable=False),
        sa.Column(
            "reminder_id",
            uuid,
            sa.ForeignKey("fermentation_reminders.id", ondelete="SET NULL"),
        ),
        sa.Column("satisfaction_source_type", sa.String(40)),
        sa.Column("satisfaction_source_id", uuid),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-addition-schedule-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requirement_id", name="uq_fermentation_addition_requirement_id"),
        sa.UniqueConstraint(
            "fermentation_session_id",
            "source_recipe_ingredient_id",
            name="uq_fermentation_addition_requirement_source",
        ),
        sa.ForeignKeyConstraint(
            ["stage_instance_id", "fermentation_session_id"],
            [
                "fermentation_stage_instances.id",
                "fermentation_stage_instances.fermentation_session_id",
            ],
            name="fk_fermentation_addition_requirement_stage_session",
        ),
    )
    op.create_index(
        "ix_fermentation_addition_requirements_session_id",
        "fermentation_addition_requirements",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_addition_requirements_stage_id",
        "fermentation_addition_requirements",
        ["stage_instance_id"],
    )
    op.create_index(
        "ix_fermentation_addition_requirements_template_id",
        "fermentation_addition_requirements",
        ["requirement_template_id"],
    )
    op.create_index(
        "ix_fermentation_addition_requirements_source_id",
        "fermentation_addition_requirements",
        ["source_recipe_ingredient_id"],
    )
    op.create_index(
        "ix_fermentation_addition_requirements_ingredient_id",
        "fermentation_addition_requirements",
        ["ingredient_id"],
    )
    op.create_index(
        "ix_fermentation_addition_requirements_reminder_id",
        "fermentation_addition_requirements",
        ["reminder_id"],
    )

    op.create_table(
        "fermentation_addition_events",
        sa.Column("id", uuid, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_instance_id",
            uuid,
            sa.ForeignKey("fermentation_stage_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requirement_id", uuid),
        sa.Column("planned", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("execution_status", sa.String(24), nullable=False),
        sa.Column("planned_amount", sa.Numeric(14, 4)),
        sa.Column("planned_unit", sa.String(16)),
        sa.Column("actual_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("actual_unit", sa.String(16), nullable=False),
        sa.Column("occurred_at", timestamp, nullable=False),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("timing_basis", sa.String(32)),
        sa.Column("timing_offset_seconds", sa.Integer()),
        sa.Column("actual_ingredient_id", uuid),
        sa.Column("actual_lot_id", uuid),
        sa.Column("note", sa.Text()),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.Column("late_entry", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("late_entry_reason", sa.Text()),
        sa.Column("available_at_original_session_completion", sa.Boolean()),
        sa.Column("terminal_state_at_recording", sa.String(32)),
        sa.Column("inventory_effect", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-addition-schedule-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "fermentation_session_id", name="uq_fermentation_addition_event_session"
        ),
        sa.ForeignKeyConstraint(
            ["stage_instance_id", "fermentation_session_id"],
            [
                "fermentation_stage_instances.id",
                "fermentation_stage_instances.fermentation_session_id",
            ],
            name="fk_fermentation_addition_event_stage_session",
        ),
    )
    op.create_index(
        "ix_fermentation_addition_events_session_id",
        "fermentation_addition_events",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_addition_events_stage_id",
        "fermentation_addition_events",
        ["stage_instance_id"],
    )
    op.create_index(
        "ix_fermentation_addition_events_requirement_id",
        "fermentation_addition_events",
        ["requirement_id"],
    )
    op.create_index(
        "ix_fermentation_addition_events_actor_user_id",
        "fermentation_addition_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_fermentation_addition_events_operation_id",
        "fermentation_addition_events",
        ["operation_id"],
    )

    op.create_table(
        "fermentation_addition_corrections",
        sa.Column("id", uuid, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_instance_id",
            uuid,
            sa.ForeignKey("fermentation_stage_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "original_addition_event_id",
            uuid,
            sa.ForeignKey("fermentation_addition_events.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("correction_of_id", uuid, nullable=False),
        sa.Column("execution_status", sa.String(24), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(14, 4)),
        sa.Column("actual_unit", sa.String(16)),
        sa.Column("occurred_at", timestamp),
        sa.Column("actual_ingredient_id", uuid),
        sa.Column("actual_lot_id", uuid),
        sa.Column("note", sa.Text()),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.Column("late_entry", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-addition-correction-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "correction_of_id", name="uq_fermentation_addition_correction_leaf"
        ),
        sa.UniqueConstraint(
            "id",
            "fermentation_session_id",
            name="uq_fermentation_addition_correction_session",
        ),
    )
    op.create_index(
        "ix_fermentation_addition_corrections_session_id",
        "fermentation_addition_corrections",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_addition_corrections_stage_id",
        "fermentation_addition_corrections",
        ["stage_instance_id"],
    )
    op.create_index(
        "ix_fermentation_addition_corrections_original_id",
        "fermentation_addition_corrections",
        ["original_addition_event_id"],
    )
    op.create_index(
        "ix_fermentation_addition_corrections_correction_of_id",
        "fermentation_addition_corrections",
        ["correction_of_id"],
    )
    op.create_index(
        "ix_fermentation_addition_corrections_actor_user_id",
        "fermentation_addition_corrections",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_fermentation_addition_corrections_operation_id",
        "fermentation_addition_corrections",
        ["operation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fermentation_addition_corrections_operation_id",
        table_name="fermentation_addition_corrections",
    )
    op.drop_index(
        "ix_fermentation_addition_corrections_actor_user_id",
        table_name="fermentation_addition_corrections",
    )
    op.drop_index(
        "ix_fermentation_addition_corrections_correction_of_id",
        table_name="fermentation_addition_corrections",
    )
    op.drop_index(
        "ix_fermentation_addition_corrections_original_id",
        table_name="fermentation_addition_corrections",
    )
    op.drop_index(
        "ix_fermentation_addition_corrections_stage_id",
        table_name="fermentation_addition_corrections",
    )
    op.drop_index(
        "ix_fermentation_addition_corrections_session_id",
        table_name="fermentation_addition_corrections",
    )
    op.drop_table("fermentation_addition_corrections")

    op.drop_index(
        "ix_fermentation_addition_events_operation_id",
        table_name="fermentation_addition_events",
    )
    op.drop_index(
        "ix_fermentation_addition_events_actor_user_id",
        table_name="fermentation_addition_events",
    )
    op.drop_index(
        "ix_fermentation_addition_events_requirement_id",
        table_name="fermentation_addition_events",
    )
    op.drop_index(
        "ix_fermentation_addition_events_stage_id",
        table_name="fermentation_addition_events",
    )
    op.drop_index(
        "ix_fermentation_addition_events_session_id",
        table_name="fermentation_addition_events",
    )
    op.drop_table("fermentation_addition_events")

    op.drop_index(
        "ix_fermentation_addition_requirements_reminder_id",
        table_name="fermentation_addition_requirements",
    )
    op.drop_index(
        "ix_fermentation_addition_requirements_ingredient_id",
        table_name="fermentation_addition_requirements",
    )
    op.drop_index(
        "ix_fermentation_addition_requirements_source_id",
        table_name="fermentation_addition_requirements",
    )
    op.drop_index(
        "ix_fermentation_addition_requirements_template_id",
        table_name="fermentation_addition_requirements",
    )
    op.drop_index(
        "ix_fermentation_addition_requirements_stage_id",
        table_name="fermentation_addition_requirements",
    )
    op.drop_index(
        "ix_fermentation_addition_requirements_session_id",
        table_name="fermentation_addition_requirements",
    )
    op.drop_table("fermentation_addition_requirements")

    op.drop_index("ix_fermentation_actions_operation_id", table_name="fermentation_actions")
    op.drop_index("ix_fermentation_actions_actor_user_id", table_name="fermentation_actions")
    op.drop_index("ix_fermentation_actions_stage_instance_id", table_name="fermentation_actions")
    op.drop_index(
        "ix_fermentation_actions_fermentation_session_id", table_name="fermentation_actions"
    )
    op.drop_table("fermentation_actions")
