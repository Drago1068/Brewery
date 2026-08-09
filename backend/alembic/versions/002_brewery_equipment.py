"""Brewery, equipment profiles, and audit foundation.

Revision ID: 002
Revises: 001
Create Date: 2026-08-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "breweries",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("preferred_units", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("default_batch_size", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("default_batch_size_unit", sa.String(length=8), nullable=False),
        sa.Column(
            "default_brewhouse_efficiency", sa.Numeric(precision=6, scale=3), nullable=False
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "equipment_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("system_type", sa.String(length=64), nullable=False),
        sa.Column("target_batch_size", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("target_batch_size_unit", sa.String(length=8), nullable=False),
        sa.Column("kettle_capacity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("kettle_capacity_unit", sa.String(length=8), nullable=False),
        sa.Column("mash_capacity", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("mash_capacity_unit", sa.String(length=8), nullable=True),
        sa.Column("boil_off_rate", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("boil_off_rate_unit", sa.String(length=16), nullable=True),
        sa.Column("trub_loss", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("trub_loss_unit", sa.String(length=8), nullable=True),
        sa.Column("fermenter_loss", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("fermenter_loss_unit", sa.String(length=8), nullable=True),
        sa.Column(
            "typical_brewhouse_efficiency", sa.Numeric(precision=6, scale=3), nullable=True
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brewery_id"], ["breweries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brewery_id", "name", name="uq_equipment_brewery_name"),
    )
    op.create_index(
        "ix_equipment_profiles_brewery_id", "equipment_profiles", ["brewery_id"]
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brewery_id"], ["breweries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_brewery_id", "audit_events", ["brewery_id"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])

    op.execute(
        "UPDATE app_meta SET value = '2', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '002', updated_at = now() WHERE key = 'schema_version'"
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_index("ix_audit_events_brewery_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_equipment_profiles_brewery_id", table_name="equipment_profiles")
    op.drop_table("equipment_profiles")
    op.drop_table("breweries")
    op.execute(
        "UPDATE app_meta SET value = '1', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '001', updated_at = now() WHERE key = 'schema_version'"
    )
