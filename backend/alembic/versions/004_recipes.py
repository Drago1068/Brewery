"""Recipe and RecipeVersion tables with snapshot components and intent.

Revision ID: 004
Revises: 003
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("style", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=False), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipes_brewery_id", "recipes", ["brewery_id"])

    op.create_table(
        "recipe_versions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("batch_size", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("batch_size_unit", sa.String(length=8), nullable=False),
        sa.Column("equipment_profile_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("brewhouse_efficiency", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("boil_time_minutes", sa.Integer(), nullable=True),
        sa.Column("mash_method", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_version_id"], ["recipe_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["equipment_profile_id"], ["equipment_profiles.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_id", "version_number", name="uq_recipe_version_number"),
    )
    op.create_index("ix_recipe_versions_recipe_id", "recipe_versions", ["recipe_id"])

    op.create_table(
        "recipe_intents",
        sa.Column("recipe_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("desired_aroma", sa.Text(), nullable=True),
        sa.Column("desired_flavor", sa.Text(), nullable=True),
        sa.Column("desired_bitterness", sa.Text(), nullable=True),
        sa.Column("desired_sweetness_dryness", sa.Text(), nullable=True),
        sa.Column("desired_body", sa.Text(), nullable=True),
        sa.Column("desired_carbonation_impression", sa.Text(), nullable=True),
        sa.Column("overall_objective", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["recipe_version_id"], ["recipe_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("recipe_version_id"),
    )

    def _component_table(name: str, extra_cols: list) -> None:
        cols = [
            sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
            sa.Column("recipe_version_id", postgresql.UUID(as_uuid=False), nullable=False),
            *extra_cols,
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(
                ["recipe_version_id"], ["recipe_versions.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        ]
        op.create_table(name, *cols)
        op.create_index(f"ix_{name}_version_id", name, ["recipe_version_id"])

    _component_table(
        "recipe_version_fermentables",
        [
            sa.Column("ingredient_id", postgresql.UUID(as_uuid=False), nullable=True),
            sa.Column("ingredient_name", sa.String(length=200), nullable=False),
            sa.Column("manufacturer", sa.String(length=200), nullable=True),
            sa.Column("amount", sa.Numeric(precision=14, scale=4), nullable=False),
            sa.Column("unit", sa.String(length=16), nullable=False),
            sa.Column("color_lovibond", sa.Numeric(precision=8, scale=3), nullable=True),
            sa.Column("potential_sg", sa.Numeric(precision=8, scale=4), nullable=True),
            sa.Column("yield_percent", sa.Numeric(precision=6, scale=3), nullable=True),
            sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="SET NULL"),
        ],
    )
    _component_table(
        "recipe_version_hops",
        [
            sa.Column("ingredient_id", postgresql.UUID(as_uuid=False), nullable=True),
            sa.Column("ingredient_name", sa.String(length=200), nullable=False),
            sa.Column("manufacturer", sa.String(length=200), nullable=True),
            sa.Column("amount", sa.Numeric(precision=14, scale=4), nullable=False),
            sa.Column("unit", sa.String(length=16), nullable=False),
            sa.Column("alpha_acid", sa.Numeric(precision=6, scale=3), nullable=True),
            sa.Column("stage", sa.String(length=32), nullable=False),
            sa.Column("time_minutes", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="SET NULL"),
        ],
    )
    _component_table(
        "recipe_version_yeasts",
        [
            sa.Column("ingredient_id", postgresql.UUID(as_uuid=False), nullable=True),
            sa.Column("ingredient_name", sa.String(length=200), nullable=False),
            sa.Column("manufacturer", sa.String(length=200), nullable=True),
            sa.Column("amount", sa.Numeric(precision=14, scale=4), nullable=True),
            sa.Column("unit", sa.String(length=16), nullable=True),
            sa.Column("expected_attenuation", sa.Numeric(precision=6, scale=3), nullable=True),
            sa.Column("temperature_min_c", sa.Numeric(precision=6, scale=2), nullable=True),
            sa.Column("temperature_max_c", sa.Numeric(precision=6, scale=2), nullable=True),
            sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="SET NULL"),
        ],
    )
    _component_table(
        "recipe_version_adjuncts",
        [
            sa.Column("ingredient_id", postgresql.UUID(as_uuid=False), nullable=True),
            sa.Column("ingredient_name", sa.String(length=200), nullable=False),
            sa.Column("amount", sa.Numeric(precision=14, scale=4), nullable=False),
            sa.Column("unit", sa.String(length=16), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="SET NULL"),
        ],
    )
    _component_table(
        "recipe_version_water_additions",
        [
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("amount", sa.Numeric(precision=14, scale=4), nullable=False),
            sa.Column("unit", sa.String(length=16), nullable=False),
            sa.Column("stage", sa.String(length=64), nullable=True),
        ],
    )
    _component_table(
        "recipe_version_mash_steps",
        [
            sa.Column("step_name", sa.String(length=120), nullable=False, server_default="Infusion"),
            sa.Column("target_temperature_c", sa.Numeric(precision=6, scale=2), nullable=False),
            sa.Column("duration_minutes", sa.Integer(), nullable=False),
            sa.Column("mash_water_volume", sa.Numeric(precision=12, scale=4), nullable=True),
            sa.Column("mash_water_unit", sa.String(length=8), nullable=True),
            sa.Column("sparge_water_volume", sa.Numeric(precision=12, scale=4), nullable=True),
            sa.Column("sparge_water_unit", sa.String(length=8), nullable=True),
        ],
    )

    op.create_table(
        "recipe_version_targets",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("recipe_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["recipe_version_id"], ["recipe_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recipe_version_targets_version_id", "recipe_version_targets", ["recipe_version_id"]
    )

    op.execute(
        "UPDATE app_meta SET value = '4', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '004', updated_at = now() WHERE key = 'schema_version'"
    )


def downgrade() -> None:
    op.drop_index("ix_recipe_version_targets_version_id", table_name="recipe_version_targets")
    op.drop_table("recipe_version_targets")
    for name in (
        "recipe_version_mash_steps",
        "recipe_version_water_additions",
        "recipe_version_adjuncts",
        "recipe_version_yeasts",
        "recipe_version_hops",
        "recipe_version_fermentables",
    ):
        op.drop_index(f"ix_{name}_version_id", table_name=name)
        op.drop_table(name)
    op.drop_table("recipe_intents")
    op.drop_index("ix_recipe_versions_recipe_id", table_name="recipe_versions")
    op.drop_table("recipe_versions")
    op.drop_index("ix_recipes_brewery_id", table_name="recipes")
    op.drop_table("recipes")
    op.execute(
        "UPDATE app_meta SET value = '3', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '003', updated_at = now() WHERE key = 'schema_version'"
    )
