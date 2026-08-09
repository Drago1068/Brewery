"""Fermentation handoff boundary records (E2A-5 / Epic 3 stub).

Revision ID: 009
Revises: 008
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fermentation_handoffs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brew_session_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brew_plan_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("recipe_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("client_submission_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("brew_day_closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["brewery_id"], ["breweries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["brew_plan_id"], ["brew_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["recipe_version_id"], ["recipe_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "brew_session_id", name="uq_fermentation_handoffs_brew_session_id"
        ),
    )
    op.create_index(
        "ix_fermentation_handoffs_brewery_id", "fermentation_handoffs", ["brewery_id"]
    )
    op.create_index(
        "ix_fermentation_handoffs_brew_plan_id",
        "fermentation_handoffs",
        ["brew_plan_id"],
    )

    op.execute(
        "UPDATE app_meta SET value = '9', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '009', updated_at = now() WHERE key = 'schema_version'"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fermentation_handoffs_brew_plan_id", table_name="fermentation_handoffs"
    )
    op.drop_index(
        "ix_fermentation_handoffs_brewery_id", table_name="fermentation_handoffs"
    )
    op.drop_table("fermentation_handoffs")
    op.execute(
        "UPDATE app_meta SET value = '8', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '008', updated_at = now() WHERE key = 'schema_version'"
    )
