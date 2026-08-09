"""Initial foundation: app_meta table and seed keys.

Revision ID: 001
Revises:
Create Date: 2026-08-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_meta",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.bulk_insert(
        sa.table(
            "app_meta",
            sa.column("key", sa.String),
            sa.column("value", sa.Text),
        ),
        [
            {"key": "product", "value": "BrewingOS"},
            {"key": "epic", "value": "1"},
            {"key": "increment", "value": "1"},
            {"key": "schema_version", "value": "001"},
        ],
    )


def downgrade() -> None:
    op.drop_table("app_meta")
