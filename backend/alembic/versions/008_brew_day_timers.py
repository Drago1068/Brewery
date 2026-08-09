"""Durable brew-day timers (E2A-4 / ADR-006).

Revision ID: 008
Revises: 007
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brew_timers",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brew_session_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("stage_occurrence_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("target_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RUNNING"),
        sa.Column("start_client_submission_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brewery_id"], ["breweries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["stage_occurrence_id"],
            ["brew_stage_occurrences.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "target_duration_seconds IS NULL OR target_duration_seconds > 0",
            name="ck_brew_timers_positive_duration",
        ),
    )
    op.create_index("ix_brew_timers_session_id", "brew_timers", ["brew_session_id"])
    op.create_index("ix_brew_timers_stage_occurrence_id", "brew_timers", ["stage_occurrence_id"])
    op.create_index("ix_brew_timers_brewery_id", "brew_timers", ["brewery_id"])

    op.execute(
        "UPDATE app_meta SET value = '8', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '008', updated_at = now() WHERE key = 'schema_version'"
    )


def downgrade() -> None:
    op.drop_index("ix_brew_timers_brewery_id", table_name="brew_timers")
    op.drop_index("ix_brew_timers_stage_occurrence_id", table_name="brew_timers")
    op.drop_index("ix_brew_timers_session_id", table_name="brew_timers")
    op.drop_table("brew_timers")
    op.execute(
        "UPDATE app_meta SET value = '7', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '007', updated_at = now() WHERE key = 'schema_version'"
    )
