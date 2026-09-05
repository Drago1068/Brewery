"""Phase 4 fermentation waivers and reminder waivable flag (P4-FR-059/060).

Revision ID: 0013_phase4_waivers
Revises: 0012_phase4_deviations
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_phase4_waivers"
down_revision: str | None = "0012_phase4_deviations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid = sa.Uuid()
timestamp = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column(
        "fermentation_reminders",
        sa.Column("waivable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_table(
        "fermentation_waivers",
        sa.Column("id", uuid, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requirement_class", sa.String(64), nullable=False),
        sa.Column("requirement_template_id", uuid, nullable=False),
        sa.Column(
            "reminder_id",
            uuid,
            sa.ForeignKey("fermentation_reminders.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("effect", sa.String(64), nullable=False),
        sa.Column("supplemental_note", sa.Text()),
        sa.Column("superseded_by_evidence_type", sa.String(40)),
        sa.Column("superseded_by_evidence_id", uuid),
        sa.Column("occurred_at", timestamp, nullable=False),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-waiver-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fermentation_waivers_fermentation_session_id",
        "fermentation_waivers",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_waivers_requirement_template_id",
        "fermentation_waivers",
        ["requirement_template_id"],
    )
    op.create_index(
        "ix_fermentation_waivers_reminder_id",
        "fermentation_waivers",
        ["reminder_id"],
    )
    op.create_index(
        "ix_fermentation_waivers_actor_user_id",
        "fermentation_waivers",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_fermentation_waivers_operation_id",
        "fermentation_waivers",
        ["operation_id"],
    )
    op.create_index(
        "uq_fermentation_waiver_active_requirement",
        "fermentation_waivers",
        ["fermentation_session_id", "requirement_template_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_fermentation_waiver_active_requirement", table_name="fermentation_waivers")
    op.drop_index("ix_fermentation_waivers_operation_id", table_name="fermentation_waivers")
    op.drop_index("ix_fermentation_waivers_actor_user_id", table_name="fermentation_waivers")
    op.drop_index("ix_fermentation_waivers_reminder_id", table_name="fermentation_waivers")
    op.drop_index(
        "ix_fermentation_waivers_requirement_template_id", table_name="fermentation_waivers"
    )
    op.drop_index(
        "ix_fermentation_waivers_fermentation_session_id", table_name="fermentation_waivers"
    )
    op.drop_table("fermentation_waivers")
    op.drop_column("fermentation_reminders", "waivable")
