"""Phase 4 plan equipment snapshot columns.

Revision ID: 0011_phase4_plan_equipment
Revises: 0010_phase4_calc_read_model_abv
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_phase4_plan_equipment"
down_revision: str | None = "0010_phase4_calc_read_model_abv"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("fermentation_sessions") as batch:
        batch.add_column(sa.Column("source_equipment_profile_id", sa.Uuid()))
        batch.add_column(sa.Column("equipment_snapshot", sa.JSON()))
        batch.create_foreign_key(
            "fk_fermentation_sessions_source_equipment",
            "equipment_profiles",
            ["source_equipment_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_fermentation_sessions_source_equipment_profile_id",
            ["source_equipment_profile_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("fermentation_sessions") as batch:
        batch.drop_index("ix_fermentation_sessions_source_equipment_profile_id")
        batch.drop_constraint("fk_fermentation_sessions_source_equipment", type_="foreignkey")
        batch.drop_column("equipment_snapshot")
        batch.drop_column("source_equipment_profile_id")
