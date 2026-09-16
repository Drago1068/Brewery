"""Phase 4 fermentation lifecycle, completion assessments, and invalidation.

Revision ID: 0006_phase4_lifecycle_completion
Revises: 0005_phase4_measurements_derived_gravity
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_phase4_lifecycle_completion"
down_revision: str | None = "0005_phase4_measurements_derived_gravity"
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
    with op.batch_alter_table("fermentation_sessions") as batch:
        batch.add_column(sa.Column("pause_origin_state", sa.String(32)))
        batch.add_column(sa.Column("paused_stage_instance_id", uuid))
        batch.add_column(sa.Column("resumed_at", timestamp))
        batch.add_column(sa.Column("fermentation_first_completed_at", timestamp))
        batch.add_column(sa.Column("fermentation_current_completed_at", timestamp))
        batch.add_column(
            sa.Column("conditioning_skipped", sa.Boolean(), server_default=sa.false(),
                nullable=False)
        )
        batch.add_column(sa.Column("conditioning_first_started_at", timestamp))
        batch.add_column(sa.Column("conditioning_current_activation_started_at", timestamp))
        batch.add_column(sa.Column("conditioning_first_completed_at", timestamp))
        batch.add_column(sa.Column("conditioning_current_completed_at", timestamp))
        batch.add_column(sa.Column("handoff_recorded_at", timestamp))
        batch.add_column(sa.Column("assessed_at", timestamp))
        batch.create_foreign_key(
            "fk_fermentation_sessions_paused_stage",
            "fermentation_stage_instances",
            ["paused_stage_instance_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("fermentation_stage_instances") as batch:
        batch.add_column(
            sa.Column("activation_ordinal", sa.Integer(), server_default="1", nullable=False)
        )

    op.create_table(
        "fermentation_completion_assessments",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assessment_kind", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-fermentation-eligibility-v1",
            nullable=False,
        ),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("predicate_results", sa.JSON(), nullable=False),
        sa.Column("evidence_summary", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("assessed_at", timestamp, nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.Column("override_reason", sa.Text()),
        sa.Column("invalidated_at", timestamp),
        sa.Column("invalidation_cause_id", uuid),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fermentation_completion_assessments_session_id",
        "fermentation_completion_assessments",
        ["fermentation_session_id"],
    )
    op.create_index(
        "uq_fermentation_completion_assessment_current",
        "fermentation_completion_assessments",
        ["fermentation_session_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true AND assessment_kind = 'FERMENTATION'"),
        sqlite_where=sa.text("is_current = true AND assessment_kind = 'FERMENTATION'"),
    )

    with op.batch_alter_table("packaging_readiness_handoffs") as batch:
        batch.drop_constraint("packaging_readiness_handoffs_fermentation_session_id_key",
            type_="unique")
        batch.add_column(sa.Column("handoff_version", sa.Integer(), server_default="1",
            nullable=False))
        batch.add_column(
            sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch.add_column(sa.Column("invalidated_at", timestamp))
        batch.add_column(sa.Column("invalidation_cause_id", uuid))
        batch.add_column(sa.Column("assessment_id", uuid))

    op.create_index(
        "uq_packaging_handoff_current_per_session",
        "packaging_readiness_handoffs",
        ["fermentation_session_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
        sqlite_where=sa.text("is_current = true"),
    )

    op.execute(
        """
        UPDATE fermentation_sessions
        SET fermentation_current_completed_at = fermentation_completed_at
        WHERE fermentation_completed_at IS NOT NULL
          AND fermentation_current_completed_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE fermentation_sessions
        SET fermentation_first_completed_at = fermentation_completed_at
        WHERE fermentation_completed_at IS NOT NULL
          AND fermentation_first_completed_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        "uq_packaging_handoff_current_per_session", table_name="packaging_readiness_handoffs")
    with op.batch_alter_table("packaging_readiness_handoffs") as batch:
        batch.drop_column("assessment_id")
        batch.drop_column("invalidation_cause_id")
        batch.drop_column("invalidated_at")
        batch.drop_column("is_current")
        batch.drop_column("handoff_version")
        batch.create_unique_constraint(
            "packaging_readiness_handoffs_fermentation_session_id_key",
            ["fermentation_session_id"],
        )

    op.drop_index(
        "uq_fermentation_completion_assessment_current",
        table_name="fermentation_completion_assessments",
    )
    op.drop_index(
        "ix_fermentation_completion_assessments_session_id",
        table_name="fermentation_completion_assessments",
    )
    op.drop_table("fermentation_completion_assessments")

    with op.batch_alter_table("fermentation_stage_instances") as batch:
        batch.drop_column("activation_ordinal")

    with op.batch_alter_table("fermentation_sessions") as batch:
        batch.drop_constraint("fk_fermentation_sessions_paused_stage", type_="foreignkey")
        batch.drop_column("assessed_at")
        batch.drop_column("handoff_recorded_at")
        batch.drop_column("conditioning_current_completed_at")
        batch.drop_column("conditioning_first_completed_at")
        batch.drop_column("conditioning_current_activation_started_at")
        batch.drop_column("conditioning_first_started_at")
        batch.drop_column("conditioning_skipped")
        batch.drop_column("fermentation_current_completed_at")
        batch.drop_column("fermentation_first_completed_at")
        batch.drop_column("resumed_at")
        batch.drop_column("paused_stage_instance_id")
        batch.drop_column("pause_origin_state")
