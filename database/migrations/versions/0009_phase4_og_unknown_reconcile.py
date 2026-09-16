"""Phase 4 unknown OG entry and reconciliation pins.

Revision ID: 0009_phase4_og_unknown_reconcile
Revises: 0008_phase4_yeast_provenance
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_phase4_og_unknown_reconcile"
down_revision: str | None = "0008_phase4_yeast_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid = sa.Uuid()
timestamp = sa.DateTime(timezone=True)


def upgrade() -> None:
    with op.batch_alter_table("fermentation_og_consumptions") as batch:
        batch.drop_constraint("fermentation_og_consumptions_fermentation_session_id_key",
            type_="unique")
        batch.alter_column("brew_measurement_id", existing_type=uuid, nullable=True)
        batch.alter_column("consumed_value", existing_type=sa.Numeric(8, 3), nullable=True)
        batch.alter_column("consumed_unit", existing_type=sa.String(16), nullable=True)
        batch.add_column(
            sa.Column(
                "og_availability",
                sa.String(16),
                server_default="KNOWN",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch.add_column(sa.Column("pin_ordinal", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(
            sa.Column(
                "brew_correction_id",
                uuid,
                sa.ForeignKey("measurements.id", ondelete="SET NULL"),
            )
        )
        batch.add_column(sa.Column("og_observed_at", timestamp))
        batch.add_column(sa.Column("actor_user_id", uuid))
        batch.add_column(sa.Column("operation_id", sa.String(64)))

    op.execute(
        sa.text(
            "UPDATE fermentation_og_consumptions "
            "SET og_availability = 'KNOWN', is_current = true, pin_ordinal = 1 "
            "WHERE og_availability IS NULL OR pin_ordinal IS NULL"
        )
    )

    op.create_index(
        "ix_fermentation_og_consumptions_session_id",
        "fermentation_og_consumptions",
        ["fermentation_session_id"],
    )
    op.create_index(
        "uq_fermentation_og_consumption_current",
        "fermentation_og_consumptions",
        ["fermentation_session_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
        sqlite_where=sa.text("is_current = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_fermentation_og_consumption_current", table_name="fermentation_og_consumptions")
    op.drop_index("ix_fermentation_og_consumptions_session_id",
        table_name="fermentation_og_consumptions")
    with op.batch_alter_table("fermentation_og_consumptions") as batch:
        batch.drop_column("operation_id")
        batch.drop_column("actor_user_id")
        batch.drop_column("og_observed_at")
        batch.drop_column("brew_correction_id")
        batch.drop_column("pin_ordinal")
        batch.drop_column("is_current")
        batch.drop_column("og_availability")
        batch.alter_column("consumed_unit", existing_type=sa.String(16), nullable=False)
        batch.alter_column("consumed_value", existing_type=sa.Numeric(8, 3), nullable=False)
        batch.alter_column("brew_measurement_id", existing_type=uuid, nullable=False)
        batch.create_unique_constraint(
            "fermentation_og_consumptions_fermentation_session_id_key",
            ["fermentation_session_id"],
        )
