"""Phase 4 fermentation notes, media, and journal export (P4-FR-062–065).

Revision ID: 0015_phase4_journal_media_export
Revises: 0014_phase4_actions_additions
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_phase4_journal_media_export"
down_revision: str | None = "0014_phase4_actions_additions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid = sa.Uuid()
timestamp = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "fermentation_notes",
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
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("operation_id", sa.String(64)),
        sa.Column("post_terminal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["stage_instance_id", "fermentation_session_id"],
            [
                "fermentation_stage_instances.id",
                "fermentation_stage_instances.fermentation_session_id",
            ],
            name="fk_fermentation_note_stage_session",
        ),
    )
    op.create_index(
        "ix_fermentation_notes_fermentation_session_id",
        "fermentation_notes",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_notes_stage_instance_id",
        "fermentation_notes",
        ["stage_instance_id"],
    )
    op.create_index(
        "ix_fermentation_notes_operation_id",
        "fermentation_notes",
        ["operation_id"],
    )

    op.create_table(
        "fermentation_attachments",
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
        ),
        sa.Column("storage_key", sa.String(80), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("byte_length", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("caption", sa.String(1000)),
        sa.Column("status", sa.String(24), server_default="FINAL", nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("operation_id", sa.String(64)),
        sa.Column("removed_at", timestamp),
        sa.Column("removal_reason", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
        sa.ForeignKeyConstraint(
            ["stage_instance_id", "fermentation_session_id"],
            [
                "fermentation_stage_instances.id",
                "fermentation_stage_instances.fermentation_session_id",
            ],
            name="fk_fermentation_attachment_stage_session",
        ),
    )
    op.create_index(
        "ix_fermentation_attachments_fermentation_session_id",
        "fermentation_attachments",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_attachments_stage_instance_id",
        "fermentation_attachments",
        ["stage_instance_id"],
    )
    op.create_index(
        "ix_fermentation_attachments_operation_id",
        "fermentation_attachments",
        ["operation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fermentation_attachments_operation_id",
        table_name="fermentation_attachments",
    )
    op.drop_index(
        "ix_fermentation_attachments_stage_instance_id",
        table_name="fermentation_attachments",
    )
    op.drop_index(
        "ix_fermentation_attachments_fermentation_session_id",
        table_name="fermentation_attachments",
    )
    op.drop_table("fermentation_attachments")

    op.drop_index("ix_fermentation_notes_operation_id", table_name="fermentation_notes")
    op.drop_index("ix_fermentation_notes_stage_instance_id", table_name="fermentation_notes")
    op.drop_index(
        "ix_fermentation_notes_fermentation_session_id",
        table_name="fermentation_notes",
    )
    op.drop_table("fermentation_notes")
