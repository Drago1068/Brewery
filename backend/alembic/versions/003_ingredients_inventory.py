"""Ingredients, specialized profiles, lots, and inventory transactions.

Revision ID: 003
Revises: 002
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("manufacturer", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_unit", sa.String(length=16), nullable=False),
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
        sa.UniqueConstraint("brewery_id", "category", "name", name="uq_ingredient_identity"),
    )
    op.create_index("ix_ingredients_brewery_id", "ingredients", ["brewery_id"])
    op.create_index("ix_ingredients_category", "ingredients", ["category"])
    op.create_index("ix_ingredients_name", "ingredients", ["name"])

    op.create_table(
        "fermentable_profiles",
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("fermentable_type", sa.String(length=32), nullable=False),
        sa.Column("color_lovibond", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("potential_sg", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("yield_percent", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ingredient_id"),
    )

    op.create_table(
        "hop_profiles",
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("hop_type", sa.String(length=32), nullable=False),
        sa.Column("default_alpha_acid", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("beta_acid", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("aroma_descriptors", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ingredient_id"),
    )

    op.create_table(
        "yeast_profiles",
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("yeast_type", sa.String(length=32), nullable=False),
        sa.Column("strain", sa.String(length=120), nullable=True),
        sa.Column("attenuation_min", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("attenuation_max", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("temperature_min_c", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("temperature_max_c", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ingredient_id"),
    )

    op.create_table(
        "ingredient_lots",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("supplier", sa.String(length=200), nullable=True),
        sa.Column("supplier_lot_number", sa.String(length=120), nullable=True),
        sa.Column("manufacturer_lot_number", sa.String(length=120), nullable=True),
        sa.Column("received_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiration_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quantity_received", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("purchase_cost", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("storage_location", sa.String(length=200), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actual_alpha_acid", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("quantity_on_hand", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column(
            "quantity_reserved",
            sa.Numeric(precision=14, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
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
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingredient_lots_brewery_id", "ingredient_lots", ["brewery_id"])
    op.create_index("ix_ingredient_lots_ingredient_id", "ingredient_lots", ["ingredient_id"])

    op.create_table(
        "inventory_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("ingredient_lot_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brewery_id"], ["breweries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["ingredient_lot_id"], ["ingredient_lots.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventory_transactions_brewery_id", "inventory_transactions", ["brewery_id"]
    )
    op.create_index(
        "ix_inventory_transactions_lot_id", "inventory_transactions", ["ingredient_lot_id"]
    )
    op.create_index(
        "ix_inventory_transactions_occurred_at", "inventory_transactions", ["occurred_at"]
    )

    op.execute(
        "UPDATE app_meta SET value = '3', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '003', updated_at = now() WHERE key = 'schema_version'"
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_transactions_occurred_at", table_name="inventory_transactions")
    op.drop_index("ix_inventory_transactions_lot_id", table_name="inventory_transactions")
    op.drop_index("ix_inventory_transactions_brewery_id", table_name="inventory_transactions")
    op.drop_table("inventory_transactions")
    op.drop_index("ix_ingredient_lots_ingredient_id", table_name="ingredient_lots")
    op.drop_index("ix_ingredient_lots_brewery_id", table_name="ingredient_lots")
    op.drop_table("ingredient_lots")
    op.drop_table("yeast_profiles")
    op.drop_table("hop_profiles")
    op.drop_table("fermentable_profiles")
    op.drop_index("ix_ingredients_name", table_name="ingredients")
    op.drop_index("ix_ingredients_category", table_name="ingredients")
    op.drop_index("ix_ingredients_brewery_id", table_name="ingredients")
    op.drop_table("ingredients")
    op.execute(
        "UPDATE app_meta SET value = '2', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '002', updated_at = now() WHERE key = 'schema_version'"
    )
