"""Phase 3 Brew-Day OS.

Revision ID: 0003_phase3_brew_day_os
Revises: 0002_phase2_brewing_core
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_phase3_brew_day_os"
down_revision: str | None = "0002_phase2_brewing_core"
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
    with op.batch_alter_table("auth_sessions") as batch:
        batch.add_column(sa.Column("csrf_token_hash", sa.String(64)))

    with op.batch_alter_table("brew_sessions") as batch:
        batch.add_column(sa.Column("paused_at", timestamp))
        batch.add_column(sa.Column("aborted_at", timestamp))
        batch.add_column(sa.Column("abort_reason", sa.Text()))
        batch.add_column(sa.Column("revision", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(sa.Column("plan_kind", sa.String(32)))
        batch.add_column(sa.Column("materialization_rule_version", sa.String(64)))
        batch.add_column(sa.Column("logical_plan_hash", sa.String(64)))
        batch.add_column(sa.Column("plan_preview_hash", sa.String(64)))
        batch.add_column(sa.Column("materialized_at", timestamp))

    op.drop_constraint("brew_stages_brew_session_id_name_key", "brew_stages", type_="unique")
    with op.batch_alter_table("brew_stages") as batch:
        batch.add_column(sa.Column("paused_at", timestamp))
        batch.add_column(sa.Column("plan_step_id", uuid))
        batch.add_column(sa.Column("canonical_stage_type", sa.String(40)))
        batch.add_column(
            sa.Column("occurrence_number", sa.Integer(), server_default="1", nullable=False)
        )
        batch.add_column(
            sa.Column("required", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch.add_column(sa.Column("runtime_occurrence_kind", sa.String(24)))
        batch.add_column(sa.Column("runtime_source_stage_id", uuid))
        batch.add_column(sa.Column("runtime_reason", sa.Text()))
        batch.add_column(sa.Column("revision", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(sa.Column("skip_reason", sa.Text()))
        batch.add_column(sa.Column("requirement_set_fingerprint", sa.String(64)))
        batch.add_column(sa.Column("active_duration_seconds", sa.Integer()))
        batch.add_column(sa.Column("wall_clock_duration_seconds", sa.Integer()))
        batch.add_column(
            sa.Column("accumulated_pause_seconds", sa.Integer(), server_default="0", nullable=False)
        )
        batch.create_foreign_key(
            "fk_brew_stages_runtime_source",
            "brew_stages",
            ["runtime_source_stage_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_unique_constraint(
            "uq_stage_occurrence", ["brew_session_id", "plan_step_id", "occurrence_number"]
        )

    with op.batch_alter_table("brew_timers") as batch:
        batch.add_column(sa.Column("brew_session_id", uuid))
        batch.add_column(
            sa.Column("clock_basis", sa.String(24), server_default="WALL_CLOCK", nullable=False)
        )
        batch.add_column(sa.Column("deadline_at", timestamp))
        batch.add_column(sa.Column("expired_at", timestamp))
        batch.add_column(sa.Column("acknowledged_at", timestamp))
        batch.add_column(sa.Column("cancelled_at", timestamp))
        batch.add_column(sa.Column("revision", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(
            sa.Column("timer_type", sa.String(40), server_default="STAGE_PRIMARY", nullable=False)
        )
        batch.add_column(sa.Column("paused_by", sa.String(32)))
        batch.add_column(
            sa.Column(
                "continues_after_stage", sa.Boolean(), server_default=sa.false(), nullable=False
            )
        )
        batch.add_column(sa.Column("replaces_timer_id", uuid))
        batch.add_column(sa.Column("addition_requirement_id", uuid))
        batch.add_column(sa.Column("cancel_reason", sa.Text()))
        batch.create_foreign_key(
            "fk_brew_timers_session",
            "brew_sessions",
            ["brew_session_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_foreign_key(
            "fk_brew_timers_replaces",
            "brew_timers",
            ["replaces_timer_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("measurements") as batch:
        batch.add_column(sa.Column("process_point", sa.String(40)))
        batch.add_column(sa.Column("raw_value", sa.Numeric(12, 4)))
        batch.add_column(sa.Column("raw_unit", sa.String(16)))
        batch.add_column(sa.Column("canonical_value", sa.Numeric(12, 4)))
        batch.add_column(sa.Column("canonical_unit", sa.String(16)))
        batch.add_column(sa.Column("recorded_at", timestamp))
        batch.add_column(sa.Column("entry_method", sa.String(32)))
        batch.add_column(sa.Column("method", sa.String(32)))
        batch.add_column(sa.Column("sample_temperature_c", sa.Numeric(6, 2)))
        batch.add_column(sa.Column("temperature_compensated", sa.Boolean()))
        batch.add_column(sa.Column("vessel", sa.String(40)))
        batch.add_column(sa.Column("conversion_model_id", sa.String(80)))
        batch.add_column(sa.Column("requirement_id", uuid))
        batch.add_column(
            sa.Column("late_entry", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(sa.Column("late_entry_reason", sa.Text()))
        batch.add_column(sa.Column("available_at_original_stage_completion", sa.Boolean()))
        batch.add_column(sa.Column("available_at_original_session_completion", sa.Boolean()))
        batch.add_column(sa.Column("context", sa.JSON()))
        batch.add_column(sa.Column("definition_version", sa.String(64)))
        batch.add_column(sa.Column("actor_user_id", uuid))
        batch.add_column(sa.Column("operation_id", sa.String(64)))

    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("brew_session_id", uuid))
        batch.add_column(sa.Column("completed_at", timestamp))
        batch.add_column(sa.Column("requirement_id", uuid))
        batch.add_column(sa.Column("requirement_template_id", uuid))
        batch.add_column(sa.Column("satisfaction_source_type", sa.String(40)))
        batch.add_column(sa.Column("satisfaction_source_id", uuid))
        batch.add_column(sa.Column("resolution_source_type", sa.String(40)))
        batch.add_column(sa.Column("resolution_source_id", uuid))
        batch.add_column(
            sa.Column("priority", sa.String(24), server_default="REQUIRED", nullable=False)
        )
        batch.add_column(sa.Column("schema_version", sa.String(64)))
        batch.add_column(sa.Column("skip_reason", sa.Text()))
        batch.add_column(sa.Column("expired_at", timestamp))
        batch.create_foreign_key(
            "fk_notifications_session",
            "brew_sessions",
            ["brew_session_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("deviations") as batch:
        batch.alter_column("measurement_id", nullable=True)
        batch.add_column(sa.Column("brew_session_id", uuid))
        batch.add_column(sa.Column("brew_stage_id", uuid))
        batch.add_column(sa.Column("comparison_status", sa.String(32)))
        batch.add_column(sa.Column("category", sa.String(40)))
        batch.add_column(sa.Column("description", sa.Text()))
        batch.add_column(sa.Column("corrective_action", sa.Text()))
        batch.add_column(sa.Column("model_id", sa.String(80)))
        batch.create_foreign_key(
            "fk_deviations_session",
            "brew_sessions",
            ["brew_session_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_foreign_key(
            "fk_deviations_stage", "brew_stages", ["brew_stage_id"], ["id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("brew_journal_events") as batch:
        batch.add_column(
            sa.Column(
                "schema_version", sa.String(64), server_default="phase3-journal-v1", nullable=False
            )
        )
        batch.add_column(sa.Column("occurred_at", timestamp))
        batch.add_column(sa.Column("recorded_at", timestamp))
        batch.add_column(sa.Column("actor_user_id", uuid))
        batch.add_column(sa.Column("operation_id", sa.String(64)))
        batch.add_column(sa.Column("correlation_id", sa.String(64)))
        batch.add_column(sa.Column("causation_id", sa.String(64)))

    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("correlation_id", sa.String(64)))
        batch.add_column(sa.Column("operation_id", sa.String(64)))

    op.create_index(
        "ix_journal_order",
        "brew_journal_events",
        ["brew_session_id", "created_at", "id"],
    )

    op.create_table(
        "brew_plan_steps",
        *common_columns(),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("plan_step_id", uuid, nullable=False),
        sa.Column("canonical_stage_type", sa.String(40), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_process_step_id", uuid),
        sa.Column("stable_source_discriminator", sa.String(80), nullable=False),
        sa.Column("expansion_rank", sa.Integer(), nullable=False),
        sa.Column("planned_same_type_ordinal", sa.Integer(), nullable=False),
        sa.Column("source_sequence", sa.Integer(), nullable=False),
        sa.Column("predecessor_plan_step_id", uuid),
        sa.Column("planned_duration_seconds", sa.Integer()),
        sa.Column("clock_basis", sa.String(24), nullable=False),
        sa.Column("sort_index", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brew_session_id", "plan_step_id"),
    )
    op.create_index("ix_brew_plan_steps_session", "brew_plan_steps", ["brew_session_id"])

    op.create_table(
        "brew_requirement_templates",
        *common_columns(),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("plan_step_id", uuid, nullable=False),
        sa.Column("requirement_template_id", uuid, nullable=False),
        sa.Column("requirement_class", sa.String(32), nullable=False),
        sa.Column("definition_key", sa.String(80), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("waivable", sa.Boolean(), nullable=False),
        sa.Column("runtime_occurrence_policy", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("addition_repeat_policy", sa.String(32)),
        sa.Column("addition_repeat_policy_version", sa.String(64)),
        sa.Column("assignment_provenance", sa.String(40)),
        sa.Column("source_addition_id", uuid),
        sa.Column("policy_fingerprint", sa.String(64)),
        sa.CheckConstraint(
            "addition_repeat_policy IS NULL OR addition_repeat_policy IN "
            "('NEVER','PLANNED_OCCURRENCES_ONLY','RUNTIME_REPEAT_ALLOWED')",
            name="ck_addition_repeat_policy",
        ),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brew_session_id", "requirement_template_id"),
    )

    op.create_table(
        "brew_stage_requirements",
        *common_columns(),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("stage_instance_id", uuid, nullable=False),
        sa.Column("requirement_template_id", uuid, nullable=False),
        sa.Column("requirement_class", sa.String(32), nullable=False),
        sa.Column("requirement_id", uuid, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("waivable", sa.Boolean(), nullable=False),
        sa.Column("provenance", sa.String(40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("satisfaction_source_type", sa.String(40)),
        sa.Column("satisfaction_source_id", uuid),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_instance_id"], ["brew_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requirement_id"),
        sa.UniqueConstraint(
            "stage_instance_id",
            "requirement_template_id",
            "requirement_class",
            name="uq_stage_requirement_template",
        ),
    )

    for table, extra in [
        (
            "brew_addition_events",
            [
                sa.Column("requirement_id", uuid, nullable=False),
                sa.Column("planned_addition_id", uuid),
                sa.Column("source_addition_id", uuid),
                sa.Column("execution_status", sa.String(24), nullable=False),
                sa.Column("planned_amount", sa.Numeric(14, 4)),
                sa.Column("planned_unit", sa.String(16)),
                sa.Column("actual_quantity", sa.Numeric(14, 4)),
                sa.Column("actual_unit", sa.String(16)),
                sa.Column("actual_executed_at", timestamp),
                sa.Column("planned_due_at", timestamp),
                sa.Column("timing_basis", sa.String(32)),
                sa.Column("timing_offset_seconds", sa.Integer()),
                sa.Column("signed_variance_seconds", sa.Integer()),
                sa.Column("actual_ingredient_id", uuid),
                sa.Column("actual_lot_id", uuid),
                sa.Column("substitution_id", uuid),
                sa.Column("note", sa.Text()),
                sa.Column("actor_user_id", uuid),
                sa.Column("operation_id", sa.String(64)),
                sa.Column("late_entry", sa.Boolean(), nullable=False),
                sa.Column("late_entry_reason", sa.Text()),
                sa.Column("available_at_original_stage_completion", sa.Boolean()),
                sa.Column("available_at_original_session_completion", sa.Boolean()),
                sa.Column("recorded_at", timestamp),
            ],
        ),
    ]:
        op.create_table(
            table,
            *common_columns(),
            sa.Column("brew_session_id", uuid, nullable=False),
            sa.Column("stage_instance_id", uuid, nullable=False),
            *extra,
            sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["stage_instance_id"], ["brew_stages.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    op.create_table(
        "brew_addition_corrections",
        *common_columns(),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("stage_instance_id", uuid, nullable=False),
        sa.Column("original_addition_event_id", uuid, nullable=False),
        sa.Column("correction_of_id", uuid, nullable=False),
        sa.Column("execution_status", sa.String(24), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(14, 4)),
        sa.Column("actual_unit", sa.String(16)),
        sa.Column("actual_executed_at", timestamp),
        sa.Column("actual_ingredient_id", uuid),
        sa.Column("actual_lot_id", uuid),
        sa.Column("substitution_id", uuid),
        sa.Column("note", sa.Text()),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", uuid),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("operation_id", sa.String(64)),
        sa.Column("rule_version", sa.String(64)),
        sa.Column("late_entry", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_instance_id"], ["brew_stages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["original_addition_event_id"], ["brew_addition_events.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correction_of_id"),
    )

    op.create_table(
        "brew_timer_revisions",
        *common_columns(),
        sa.Column("timer_id", uuid, nullable=False),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("former_deadline_at", timestamp),
        sa.Column("former_duration_seconds", sa.Integer()),
        sa.Column("new_deadline_at", timestamp),
        sa.Column("new_duration_seconds", sa.Integer()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", uuid),
        sa.Column("operation_id", sa.String(64)),
        sa.ForeignKeyConstraint(["timer_id"], ["brew_timers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "brew_waivers",
        *common_columns(),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("stage_instance_id", uuid, nullable=False),
        sa.Column("requirement_id", uuid, nullable=False),
        sa.Column("requirement_kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.Column("superseded_by_id", uuid),
        sa.Column("superseded_by_type", sa.String(40)),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_instance_id"], ["brew_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "brew_notes",
        *common_columns(),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("stage_instance_id", uuid),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("operation_id", sa.String(64)),
        sa.Column("correction_of_id", uuid),
        sa.Column("post_terminal", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_instance_id"], ["brew_stages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["correction_of_id"], ["brew_notes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "brew_attachments",
        *common_columns(),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("stage_instance_id", uuid),
        sa.Column("storage_key", sa.String(80), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("byte_length", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("caption", sa.String(1000)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("operation_id", sa.String(64)),
        sa.Column("removed_at", timestamp),
        sa.Column("removal_reason", sa.Text()),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_instance_id"], ["brew_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )

    op.create_table(
        "brew_operations",
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
        sa.Column("tombstone", sa.Boolean(), nullable=False),
        sa.Column("completed_at", timestamp),
        sa.Column("retained_until", timestamp),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_user_id",
            "use_case",
            "aggregate_type",
            "aggregate_id",
            "operation_id",
            name="uq_phase3_operation_scope",
        ),
    )

    op.create_table(
        "brew_pitch_handoffs",
        *common_columns(),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("pitched_at", timestamp, nullable=False),
        sa.Column("pitch_temperature_c", sa.Numeric(6, 2)),
        sa.Column("yeast_addition_note", sa.Text(), nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("schema_version", sa.String(64)),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brew_session_id"),
    )

    op.create_table(
        "brew_reminder_history",
        *common_columns(),
        sa.Column("reminder_id", uuid, nullable=False),
        sa.Column("prior_status", sa.String(24), nullable=False),
        sa.Column("new_status", sa.String(24), nullable=False),
        sa.Column("cause", sa.String(80), nullable=False),
        sa.Column("actor_user_id", uuid),
        sa.Column("operation_id", sa.String(64)),
        sa.ForeignKeyConstraint(["reminder_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "uq_brew_sessions_one_active_or_paused",
        "brew_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE','PAUSED')"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION phase3_protect_plan_steps() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'immutable brew plan step';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER brew_plan_steps_immutable
        BEFORE UPDATE OR DELETE ON brew_plan_steps
        FOR EACH ROW EXECUTE FUNCTION phase3_protect_plan_steps();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION phase3_protect_requirement_templates() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'immutable requirement template';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER brew_requirement_templates_immutable
        BEFORE UPDATE OR DELETE ON brew_requirement_templates
        FOR EACH ROW EXECUTE FUNCTION phase3_protect_requirement_templates();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS brew_requirement_templates_immutable ON brew_requirement_templates"
    )
    op.execute("DROP TRIGGER IF EXISTS brew_plan_steps_immutable ON brew_plan_steps")
    op.execute("DROP FUNCTION IF EXISTS phase3_protect_requirement_templates()")
    op.execute("DROP FUNCTION IF EXISTS phase3_protect_plan_steps()")
    op.drop_index("uq_brew_sessions_one_active_or_paused", table_name="brew_sessions")
    for table in [
        "brew_reminder_history",
        "brew_pitch_handoffs",
        "brew_operations",
        "brew_attachments",
        "brew_notes",
        "brew_waivers",
        "brew_timer_revisions",
        "brew_addition_corrections",
        "brew_addition_events",
        "brew_stage_requirements",
        "brew_requirement_templates",
        "brew_plan_steps",
    ]:
        op.drop_table(table)
    op.drop_index("ix_journal_order", table_name="brew_journal_events")
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_column("operation_id")
        batch.drop_column("correlation_id")
    with op.batch_alter_table("brew_journal_events") as batch:
        batch.drop_column("causation_id")
        batch.drop_column("correlation_id")
        batch.drop_column("operation_id")
        batch.drop_column("actor_user_id")
        batch.drop_column("recorded_at")
        batch.drop_column("occurred_at")
        batch.drop_column("schema_version")
    with op.batch_alter_table("deviations") as batch:
        batch.drop_constraint("fk_deviations_stage", type_="foreignkey")
        batch.drop_constraint("fk_deviations_session", type_="foreignkey")
        batch.drop_column("model_id")
        batch.drop_column("corrective_action")
        batch.drop_column("description")
        batch.drop_column("category")
        batch.drop_column("comparison_status")
        batch.drop_column("brew_stage_id")
        batch.drop_column("brew_session_id")
        batch.alter_column("measurement_id", nullable=False)
    with op.batch_alter_table("notifications") as batch:
        batch.drop_constraint("fk_notifications_session", type_="foreignkey")
        batch.drop_column("expired_at")
        batch.drop_column("skip_reason")
        batch.drop_column("schema_version")
        batch.drop_column("priority")
        batch.drop_column("resolution_source_id")
        batch.drop_column("resolution_source_type")
        batch.drop_column("satisfaction_source_id")
        batch.drop_column("satisfaction_source_type")
        batch.drop_column("requirement_template_id")
        batch.drop_column("requirement_id")
        batch.drop_column("completed_at")
        batch.drop_column("brew_session_id")
    with op.batch_alter_table("measurements") as batch:
        batch.drop_column("operation_id")
        batch.drop_column("actor_user_id")
        batch.drop_column("definition_version")
        batch.drop_column("context")
        batch.drop_column("available_at_original_session_completion")
        batch.drop_column("available_at_original_stage_completion")
        batch.drop_column("late_entry_reason")
        batch.drop_column("late_entry")
        batch.drop_column("requirement_id")
        batch.drop_column("conversion_model_id")
        batch.drop_column("vessel")
        batch.drop_column("temperature_compensated")
        batch.drop_column("sample_temperature_c")
        batch.drop_column("method")
        batch.drop_column("entry_method")
        batch.drop_column("recorded_at")
        batch.drop_column("canonical_unit")
        batch.drop_column("canonical_value")
        batch.drop_column("raw_unit")
        batch.drop_column("raw_value")
        batch.drop_column("process_point")
    with op.batch_alter_table("brew_timers") as batch:
        batch.drop_constraint("fk_brew_timers_replaces", type_="foreignkey")
        batch.drop_constraint("fk_brew_timers_session", type_="foreignkey")
        batch.drop_column("cancel_reason")
        batch.drop_column("addition_requirement_id")
        batch.drop_column("replaces_timer_id")
        batch.drop_column("continues_after_stage")
        batch.drop_column("paused_by")
        batch.drop_column("timer_type")
        batch.drop_column("revision")
        batch.drop_column("cancelled_at")
        batch.drop_column("acknowledged_at")
        batch.drop_column("expired_at")
        batch.drop_column("deadline_at")
        batch.drop_column("clock_basis")
        batch.drop_column("brew_session_id")
    with op.batch_alter_table("brew_stages") as batch:
        batch.drop_constraint("uq_stage_occurrence", type_="unique")
        batch.drop_constraint("fk_brew_stages_runtime_source", type_="foreignkey")
        batch.drop_column("accumulated_pause_seconds")
        batch.drop_column("wall_clock_duration_seconds")
        batch.drop_column("active_duration_seconds")
        batch.drop_column("requirement_set_fingerprint")
        batch.drop_column("skip_reason")
        batch.drop_column("revision")
        batch.drop_column("runtime_reason")
        batch.drop_column("runtime_source_stage_id")
        batch.drop_column("runtime_occurrence_kind")
        batch.drop_column("required")
        batch.drop_column("occurrence_number")
        batch.drop_column("canonical_stage_type")
        batch.drop_column("plan_step_id")
        batch.drop_column("paused_at")
    op.create_unique_constraint(
        "brew_stages_brew_session_id_name_key", "brew_stages", ["brew_session_id", "name"]
    )
    with op.batch_alter_table("brew_sessions") as batch:
        batch.drop_column("materialized_at")
        batch.drop_column("plan_preview_hash")
        batch.drop_column("logical_plan_hash")
        batch.drop_column("materialization_rule_version")
        batch.drop_column("plan_kind")
        batch.drop_column("revision")
        batch.drop_column("abort_reason")
        batch.drop_column("aborted_at")
        batch.drop_column("paused_at")
    with op.batch_alter_table("auth_sessions") as batch:
        batch.drop_column("csrf_token_hash")
