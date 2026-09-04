"""Phase 4 derived-gravity ABV read-model closure.

Revision ID: 0010_phase4_calc_read_model_abv
Revises: 0009_phase4_og_unknown_reconcile
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_phase4_calc_read_model_abv"
down_revision: str | None = "0009_phase4_og_unknown_reconcile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("fermentation_derived_gravity_snapshots") as batch:
        batch.add_column(sa.Column("abv_percent", sa.Numeric(8, 4)))


def downgrade() -> None:
    with op.batch_alter_table("fermentation_derived_gravity_snapshots") as batch:
        batch.drop_column("abv_percent")
