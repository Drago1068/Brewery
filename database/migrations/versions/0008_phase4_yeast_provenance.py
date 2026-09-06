"""Phase 4 yeast provenance and pitch-history lineage.

Revision ID: 0008_phase4_yeast_provenance
Revises: 0007_phase4_timers_reminders
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_phase4_yeast_provenance"
down_revision: str | None = "0007_phase4_timers_reminders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid = sa.Uuid()
timestamp = sa.DateTime(timezone=True)

_JSON_EMPTY = sa.text("'{}'::json")


def common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", uuid, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
    ]


def upgrade() -> None:
    # Food-pair/FK for optional same-owner yeast lot linkage. Snapshotted
    # metadata is stored independently so live lot edits never rewrite it.
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column("ingredient_lot_id", uuid, sa.ForeignKey("ingredient_lots.id", ondelete="SET NULL")),
    )
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column("lot_snapshot", sa.JSON(), server_default=_JSON_EMPTY, nullable=False),
    )
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column("preparation_method_note", sa.Text()),
    )
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column("pitch_inputs", sa.JSON(), server_default=_JSON_EMPTY, nullable=False),
    )
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column("field_provenance", sa.JSON(), server_default=_JSON_EMPTY, nullable=False),
    )
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column(
            "source_fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column(
            "source_yeast_reference_id",
            uuid,
            sa.ForeignKey("fermentation_yeast_pitch_references.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column("declaration_note", sa.Text()),
    )
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column("actor_user_id", uuid),
    )
    op.add_column(
        "fermentation_yeast_pitch_references",
        sa.Column("enriched_at", timestamp),
    )
    op.create_index(
        "ix_fermentation_yeast_pitch_references_lot_id",
        "fermentation_yeast_pitch_references",
        ["ingredient_lot_id"],
    )
    op.create_index(
        "ix_fermentation_yeast_pitch_references_source_session_id",
        "fermentation_yeast_pitch_references",
        ["source_fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_yeast_pitch_references_source_ref_id",
        "fermentation_yeast_pitch_references",
        ["source_yeast_reference_id"],
    )
    op.create_index(
        "ix_fermentation_yeast_pitch_references_actor_user_id",
        "fermentation_yeast_pitch_references",
        ["actor_user_id"],
    )

    op.create_table(
        "fermentation_yeast_reference_history",
        *common_columns(),
        sa.Column(
            "fermentation_yeast_reference_id",
            uuid,
            sa.ForeignKey("fermentation_yeast_pitch_references.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("prior_snapshot", sa.JSON(), nullable=False),
        sa.Column("new_snapshot", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", uuid),
        sa.Column("operation_id", sa.String(64)),
        sa.Column("reason", sa.Text()),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fermentation_yeast_reference_history_ref_id",
        "fermentation_yeast_reference_history",
        ["fermentation_yeast_reference_id"],
    )
    op.create_index(
        "ix_fermentation_yeast_reference_history_session_id",
        "fermentation_yeast_reference_history",
        ["fermentation_session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fermentation_yeast_reference_history_session_id",
        table_name="fermentation_yeast_reference_history",
    )
    op.drop_index(
        "ix_fermentation_yeast_reference_history_ref_id",
        table_name="fermentation_yeast_reference_history",
    )
    op.drop_table("fermentation_yeast_reference_history")

    op.drop_index(
        "ix_fermentation_yeast_pitch_references_actor_user_id",
        table_name="fermentation_yeast_pitch_references",
    )
    op.drop_index(
        "ix_fermentation_yeast_pitch_references_source_ref_id",
        table_name="fermentation_yeast_pitch_references",
    )
    op.drop_index(
        "ix_fermentation_yeast_pitch_references_source_session_id",
        table_name="fermentation_yeast_pitch_references",
    )
    op.drop_index(
        "ix_fermentation_yeast_pitch_references_lot_id",
        table_name="fermentation_yeast_pitch_references",
    )
    op.drop_column("fermentation_yeast_pitch_references", "enriched_at")
    op.drop_column("fermentation_yeast_pitch_references", "actor_user_id")
    op.drop_column("fermentation_yeast_pitch_references", "revision")
    op.drop_column("fermentation_yeast_pitch_references", "declaration_note")
    op.drop_column("fermentation_yeast_pitch_references", "source_yeast_reference_id")
    op.drop_column("fermentation_yeast_pitch_references", "source_fermentation_session_id")
    op.drop_column("fermentation_yeast_pitch_references", "field_provenance")
    op.drop_column("fermentation_yeast_pitch_references", "pitch_inputs")
    op.drop_column("fermentation_yeast_pitch_references", "preparation_method_note")
    op.drop_column("fermentation_yeast_pitch_references", "lot_snapshot")
    op.drop_column("fermentation_yeast_pitch_references", "ingredient_lot_id")