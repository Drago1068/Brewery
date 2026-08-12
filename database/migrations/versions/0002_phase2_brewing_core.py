"""Phase 2 brewing core.

Revision ID: 0002_phase2_brewing_core
Revises: 0001_phase1a
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase2_brewing_core"
down_revision: str | None = "0001_phase1a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid = sa.Uuid()
timestamp = sa.DateTime(timezone=True)


def common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", uuid, nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "equipment_profiles",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("default_batch_liters", sa.Numeric(10, 3), nullable=False),
        sa.Column("preferred_volume_unit", sa.String(16), nullable=False),
        sa.Column("preferred_temperature_unit", sa.String(16), nullable=False),
        sa.Column("brewhouse_efficiency", sa.Numeric(6, 5), nullable=False),
        sa.Column("mash_efficiency", sa.Numeric(6, 5)),
        sa.Column("boil_off_liters_per_hour", sa.Numeric(10, 3), nullable=False),
        sa.Column("kettle_loss_liters", sa.Numeric(10, 3), nullable=False),
        sa.Column("mash_tun_deadspace_liters", sa.Numeric(10, 3), nullable=False),
        sa.Column("fermenter_loss_liters", sa.Numeric(10, 3), nullable=False),
        sa.Column("packaging_loss_liters", sa.Numeric(10, 3), nullable=False),
        sa.Column("grain_absorption_liters_per_kg", sa.Numeric(10, 4), nullable=False),
        sa.Column("hop_absorption_liters_per_kg", sa.Numeric(10, 4), nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.CheckConstraint("default_batch_liters > 0", name="ck_equipment_batch_positive"),
        sa.CheckConstraint(
            "brewhouse_efficiency > 0 AND brewhouse_efficiency <= 1",
            name="ck_equipment_brewhouse_efficiency",
        ),
        sa.CheckConstraint(
            "mash_efficiency IS NULL OR (mash_efficiency > 0 AND mash_efficiency <= 1)",
            name="ck_equipment_mash_efficiency",
        ),
        sa.CheckConstraint(
            "boil_off_liters_per_hour >= 0 AND kettle_loss_liters >= 0 AND "
            "mash_tun_deadspace_liters >= 0 AND fermenter_loss_liters >= 0 AND "
            "packaging_loss_liters >= 0 AND grain_absorption_liters_per_kg >= 0 AND "
            "hop_absorption_liters_per_kg >= 0",
            name="ck_equipment_nonnegative_losses",
        ),
        sa.CheckConstraint(
            "preferred_volume_unit IN ('L', 'gal')", name="ck_equipment_volume_unit"
        ),
        sa.CheckConstraint(
            "preferred_temperature_unit IN ('degC', 'degF')", name="ck_equipment_temp_unit"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name"),
    )
    op.create_index("ix_equipment_profiles_owner_id", "equipment_profiles", ["owner_id"])

    op.create_table(
        "ingredients",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("manufacturer", sa.String(180)),
        sa.Column("canonical_unit", sa.String(16), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint(
            "category IN ('FERMENTABLE','HOP','YEAST','WATER_ADDITION','ADJUNCT',"
            "'FINING','NUTRIENT','MISCELLANEOUS')",
            name="ck_ingredient_category",
        ),
        sa.CheckConstraint("canonical_unit IN ('g', 'L', 'each')", name="ck_ingredient_unit"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name"),
    )
    op.create_index("ix_ingredients_owner_id", "ingredients", ["owner_id"])
    op.create_index("ix_ingredients_category", "ingredients", ["category"])

    op.create_table(
        "suppliers",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name"),
    )
    op.create_index("ix_suppliers_owner_id", "suppliers", ["owner_id"])

    op.create_table(
        "inventory_locations",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name"),
    )
    op.create_index("ix_inventory_locations_owner_id", "inventory_locations", ["owner_id"])

    with op.batch_alter_table("recipe_versions") as batch:
        batch.add_column(sa.Column("equipment_profile_id", uuid))
        batch.add_column(sa.Column("style_name", sa.String(160)))
        batch.add_column(sa.Column("bjcp_category", sa.String(80)))
        batch.add_column(sa.Column("batch_size_liters", sa.Numeric(10, 3)))
        batch.add_column(sa.Column("target_og", sa.Numeric(6, 4)))
        batch.add_column(sa.Column("target_fg", sa.Numeric(6, 4)))
        batch.add_column(sa.Column("target_abv_percent", sa.Numeric(7, 3)))
        batch.add_column(sa.Column("target_ibu", sa.Numeric(8, 3)))
        batch.add_column(sa.Column("target_color_srm", sa.Numeric(8, 3)))
        batch.add_column(sa.Column("target_carbonation_volumes", sa.Numeric(6, 3)))
        batch.add_column(sa.Column("boil_duration_minutes", sa.Integer()))
        batch.add_column(sa.Column("apparent_attenuation", sa.Numeric(6, 5)))
        batch.add_column(sa.Column("equipment_snapshot", sa.JSON()))
        batch.add_column(sa.Column("calculation_inputs", sa.JSON()))
        batch.add_column(sa.Column("calculation_outputs", sa.JSON()))
        batch.add_column(sa.Column("model_versions", sa.JSON()))
        batch.add_column(sa.Column("notes", sa.Text()))
        batch.create_foreign_key(
            "fk_recipe_versions_equipment",
            "equipment_profiles",
            ["equipment_profile_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_recipe_batch_positive", "batch_size_liters IS NULL OR batch_size_liters > 0"
        )
        batch.create_check_constraint(
            "ck_recipe_attenuation",
            "apparent_attenuation IS NULL OR "
            "(apparent_attenuation >= 0 AND apparent_attenuation <= 1)",
        )
    op.create_index(
        "ix_recipe_versions_equipment_profile_id", "recipe_versions", ["equipment_profile_id"]
    )

    op.create_table(
        "ingredient_lots",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("ingredient_id", uuid, nullable=False),
        sa.Column("supplier_id", uuid),
        sa.Column("lot_code", sa.String(160), nullable=False),
        sa.Column("purchase_date", sa.Date()),
        sa.Column("received_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("cost", sa.Numeric(14, 2)),
        sa.Column("best_by_date", sa.Date()),
        sa.Column("hop_alpha_acid_percent", sa.Numeric(6, 3)),
        sa.Column("yeast_manufactured_date", sa.Date()),
        sa.Column("yeast_expiration_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("received_quantity > 0", name="ck_lot_quantity_positive"),
        sa.CheckConstraint("unit IN ('g', 'L', 'each')", name="ck_lot_unit"),
        sa.CheckConstraint(
            "hop_alpha_acid_percent IS NULL OR "
            "(hop_alpha_acid_percent >= 0 AND hop_alpha_acid_percent <= 100)",
            name="ck_lot_alpha_acid",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "lot_code"),
    )
    for column in ("owner_id", "ingredient_id", "supplier_id"):
        op.create_index(f"ix_ingredient_lots_{column}", "ingredient_lots", [column])

    op.create_table(
        "supplier_items",
        *common_columns(),
        sa.Column("supplier_id", uuid, nullable=False),
        sa.Column("ingredient_id", uuid, nullable=False),
        sa.Column("sku", sa.String(120), nullable=False),
        sa.Column("package_quantity", sa.Numeric(14, 4)),
        sa.Column("unit", sa.String(16)),
        sa.Column("unit_cost", sa.Numeric(14, 4)),
        sa.CheckConstraint(
            "package_quantity IS NULL OR package_quantity > 0", name="ck_supplier_package_positive"
        ),
        sa.CheckConstraint(
            "unit IS NULL OR unit IN ('g', 'L', 'each')", name="ck_supplier_item_unit"
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_id", "sku"),
    )
    op.create_index("ix_supplier_items_supplier_id", "supplier_items", ["supplier_id"])
    op.create_index("ix_supplier_items_ingredient_id", "supplier_items", ["ingredient_id"])

    op.create_table(
        "recipe_ingredients",
        *common_columns(),
        sa.Column("recipe_version_id", uuid, nullable=False),
        sa.Column("ingredient_id", uuid, nullable=False),
        sa.Column("ingredient_lot_id", uuid),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("use_stage", sa.String(40), nullable=False),
        sa.Column("timing_minutes", sa.Integer()),
        sa.Column("percentage", sa.Numeric(7, 4)),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("amount > 0", name="ck_recipe_ingredient_amount"),
        sa.CheckConstraint("unit IN ('g', 'L', 'each')", name="ck_recipe_ingredient_unit"),
        sa.CheckConstraint(
            "timing_minutes IS NULL OR timing_minutes >= 0", name="ck_recipe_ingredient_timing"
        ),
        sa.CheckConstraint(
            "percentage IS NULL OR (percentage >= 0 AND percentage <= 100)",
            name="ck_recipe_ingredient_percentage",
        ),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ingredient_lot_id"], ["ingredient_lots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("recipe_version_id", "ingredient_id", "ingredient_lot_id"):
        op.create_index(f"ix_recipe_ingredients_{column}", "recipe_ingredients", [column])

    op.create_table(
        "recipe_process_steps",
        *common_columns(),
        sa.Column("recipe_version_id", uuid, nullable=False),
        sa.Column("step_type", sa.String(40), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("duration_minutes", sa.Integer()),
        sa.Column("temperature_c", sa.Numeric(7, 3)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint("sequence >= 0", name="ck_process_step_sequence"),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes >= 0", name="ck_process_step_duration"
        ),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_version_id", "sequence"),
    )
    op.create_index(
        "ix_recipe_process_steps_recipe_version_id", "recipe_process_steps", ["recipe_version_id"]
    )

    op.create_table(
        "water_profile_targets",
        *common_columns(),
        sa.Column("recipe_version_id", uuid, nullable=False),
        *[
            sa.Column(f"{ion}_ppm", sa.Numeric(10, 3))
            for ion in ("calcium", "magnesium", "sodium", "chloride", "sulfate", "bicarbonate")
        ],
        sa.CheckConstraint(
            "(calcium_ppm IS NULL OR calcium_ppm >= 0) AND "
            "(magnesium_ppm IS NULL OR magnesium_ppm >= 0) AND "
            "(sodium_ppm IS NULL OR sodium_ppm >= 0) AND "
            "(chloride_ppm IS NULL OR chloride_ppm >= 0) AND "
            "(sulfate_ppm IS NULL OR sulfate_ppm >= 0) AND "
            "(bicarbonate_ppm IS NULL OR bicarbonate_ppm >= 0)",
            name="ck_water_ions_nonnegative",
        ),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_version_id"),
    )

    op.create_table(
        "inventory_transactions",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("ingredient_id", uuid, nullable=False),
        sa.Column("ingredient_lot_id", uuid),
        sa.Column("location_id", uuid),
        sa.Column("destination_location_id", uuid),
        sa.Column("transaction_type", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("reference_type", sa.String(80)),
        sa.Column("reference_id", uuid),
        sa.Column("note", sa.Text()),
        sa.CheckConstraint(
            "transaction_type IN "
            "('PURCHASE','ADJUSTMENT','RESERVATION','RELEASE','CONSUMPTION',"
            "'WASTE','TRANSFER','RETURN')",
            name="ck_inventory_transaction_type",
        ),
        sa.CheckConstraint("unit IN ('g', 'L', 'each')", name="ck_inventory_transaction_unit"),
        sa.CheckConstraint(
            "(transaction_type = 'ADJUSTMENT' AND quantity <> 0) OR "
            "(transaction_type <> 'ADJUSTMENT' AND quantity > 0)",
            name="ck_inventory_transaction_quantity",
        ),
        sa.CheckConstraint(
            "(transaction_type = 'TRANSFER' AND location_id IS NOT NULL AND "
            "destination_location_id IS NOT NULL "
            "AND location_id <> destination_location_id) OR "
            "(transaction_type <> 'TRANSFER' AND destination_location_id IS NULL)",
            name="ck_inventory_transfer_locations",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ingredient_lot_id"], ["ingredient_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["destination_location_id"], ["inventory_locations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "owner_id",
        "ingredient_id",
        "ingredient_lot_id",
        "location_id",
        "destination_location_id",
        "transaction_type",
        "reference_id",
    ):
        op.create_index(f"ix_inventory_transactions_{column}", "inventory_transactions", [column])

    op.create_table(
        "inventory_reservations",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("ingredient_id", uuid, nullable=False),
        sa.Column("ingredient_lot_id", uuid),
        sa.Column("location_id", uuid),
        sa.Column("recipe_version_id", uuid),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("released_at", timestamp),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_reservation_quantity"),
        sa.CheckConstraint("unit IN ('g', 'L', 'each')", name="ck_inventory_reservation_unit"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','RELEASED','CONSUMED')", name="ck_inventory_reservation_status"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ingredient_lot_id"], ["ingredient_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "owner_id",
        "ingredient_id",
        "ingredient_lot_id",
        "location_id",
        "recipe_version_id",
        "status",
    ):
        op.create_index(f"ix_inventory_reservations_{column}", "inventory_reservations", [column])

    op.create_table(
        "safety_stock_policies",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("ingredient_id", uuid, nullable=False),
        sa.Column("threshold_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.CheckConstraint("threshold_quantity >= 0", name="ck_safety_stock_threshold"),
        sa.CheckConstraint("unit IN ('g', 'L', 'each')", name="ck_safety_stock_unit"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ingredient_id"),
    )
    op.create_index("ix_safety_stock_policies_owner_id", "safety_stock_policies", ["owner_id"])

    op.create_table(
        "ingredient_substitutions",
        *common_columns(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("original_ingredient_id", uuid, nullable=False),
        sa.Column("substitute_ingredient_id", uuid, nullable=False),
        sa.Column("conversion_ratio", sa.Numeric(10, 5), nullable=False),
        sa.Column("process_impact", sa.Text(), nullable=False),
        sa.Column("flavor_impact", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("requires_brewer_approval", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "original_ingredient_id <> substitute_ingredient_id", name="ck_substitution_distinct"
        ),
        sa.CheckConstraint("conversion_ratio > 0", name="ck_substitution_ratio"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_substitution_confidence"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["original_ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["substitute_ingredient_id"], ["ingredients.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "original_ingredient_id", "substitute_ingredient_id"),
    )
    for column in ("owner_id", "original_ingredient_id", "substitute_ingredient_id"):
        op.create_index(
            f"ix_ingredient_substitutions_{column}", "ingredient_substitutions", [column]
        )

    op.execute(
        """
        CREATE FUNCTION protect_inventory_ledger() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'Inventory transactions are append-only';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER inventory_ledger_immutable
        BEFORE UPDATE OR DELETE ON inventory_transactions
        FOR EACH ROW EXECUTE FUNCTION protect_inventory_ledger();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS inventory_ledger_immutable ON inventory_transactions")
    op.execute("DROP FUNCTION IF EXISTS protect_inventory_ledger")
    for table in (
        "ingredient_substitutions",
        "safety_stock_policies",
        "inventory_reservations",
        "inventory_transactions",
        "water_profile_targets",
        "recipe_process_steps",
        "recipe_ingredients",
        "supplier_items",
        "ingredient_lots",
    ):
        op.drop_table(table)
    op.drop_index("ix_recipe_versions_equipment_profile_id", table_name="recipe_versions")
    with op.batch_alter_table("recipe_versions") as batch:
        batch.drop_constraint("fk_recipe_versions_equipment", type_="foreignkey")
        for column in (
            "notes",
            "model_versions",
            "calculation_outputs",
            "calculation_inputs",
            "equipment_snapshot",
            "apparent_attenuation",
            "boil_duration_minutes",
            "target_carbonation_volumes",
            "target_color_srm",
            "target_ibu",
            "target_abv_percent",
            "target_fg",
            "target_og",
            "batch_size_liters",
            "bjcp_category",
            "style_name",
            "equipment_profile_id",
        ):
            batch.drop_column(column)
    for table in ("inventory_locations", "suppliers", "ingredients", "equipment_profiles"):
        op.drop_table(table)
