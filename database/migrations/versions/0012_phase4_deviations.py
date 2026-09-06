"""Phase 4 fermentation deviations (§22 / P4-FR-058).

Revision ID: 0012_phase4_deviations
Revises: 0011_phase4_plan_equipment
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_phase4_deviations"
down_revision: str | None = "0011_phase4_plan_equipment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid = sa.Uuid()
timestamp = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "fermentation_deviations",
        sa.Column("id", uuid, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("deviation_class", sa.String(40), nullable=False),
        sa.Column("origin", sa.String(24), nullable=False),
        sa.Column("derived_identity", uuid),
        sa.Column("source_evidence_id", uuid),
        sa.Column("plan_hash", sa.String(64)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("exceeded", sa.Boolean(), nullable=False),
        sa.Column("measured_value", sa.Numeric(14, 6)),
        sa.Column("target_value", sa.Numeric(14, 6)),
        sa.Column("tolerance_value", sa.Numeric(14, 6)),
        sa.Column("variance", sa.Numeric(14, 6)),
        sa.Column("unit", sa.String(16)),
        sa.Column("comparison_payload", sa.JSON(), nullable=False),
        sa.Column("resolution_note", sa.Text()),
        sa.Column(
            "supersedes_id",
            uuid,
            sa.ForeignKey("fermentation_deviations.id", ondelete="SET NULL"),
        ),
        sa.Column("occurred_at", timestamp, nullable=False),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("actor_user_id", uuid),
        sa.Column("operation_id", sa.String(64)),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-deviation-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fermentation_deviations_fermentation_session_id",
        "fermentation_deviations",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_deviations_derived_identity",
        "fermentation_deviations",
        ["derived_identity"],
    )
    op.create_index(
        "ix_fermentation_deviations_source_evidence_id",
        "fermentation_deviations",
        ["source_evidence_id"],
    )
    op.create_index(
        "ix_fermentation_deviations_actor_user_id",
        "fermentation_deviations",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_fermentation_deviations_operation_id",
        "fermentation_deviations",
        ["operation_id"],
    )
    op.create_index(
        "uq_fermentation_deviation_current_leaf",
        "fermentation_deviations",
        ["fermentation_session_id", "deviation_class", "source_evidence_id"],
        unique=True,
        postgresql_where=sa.text("status = 'CURRENT'"),
        sqlite_where=sa.text("status = 'CURRENT'"),
    )


def downgrade() -> None:
    op.drop_index("uq_fermentation_deviation_current_leaf", table_name="fermentation_deviations")
    op.drop_index("ix_fermentation_deviations_operation_id", table_name="fermentation_deviations")
    op.drop_index("ix_fermentation_deviations_actor_user_id", table_name="fermentation_deviations")
    op.drop_index(
        "ix_fermentation_deviations_source_evidence_id", table_name="fermentation_deviations"
    )
    op.drop_index(
        "ix_fermentation_deviations_derived_identity", table_name="fermentation_deviations"
    )
    op.drop_index(
        "ix_fermentation_deviations_fermentation_session_id",
        table_name="fermentation_deviations",
    )
    op.drop_table("fermentation_deviations")
