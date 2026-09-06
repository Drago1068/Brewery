"""Phase 4 measurements, corrections, and derived gravity persistence.

Revision ID: 0005_phase4_measurements_derived_gravity
Revises: 0004_phase4_fermentation_conditioning_yeast
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_phase4_measurements_derived_gravity"
down_revision: str | None = "0004_phase4_fermentation_conditioning_yeast"
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
    with op.batch_alter_table("fermentation_stage_instances") as batch:
        batch.add_column(sa.Column("first_started_at", timestamp))
        batch.add_column(sa.Column("first_completed_at", timestamp))
        batch.add_column(sa.Column("current_activation_started_at", timestamp))
        batch.add_column(sa.Column("current_completed_at", timestamp))
        batch.create_unique_constraint(
            "uq_fermentation_stage_session", ["id", "fermentation_session_id"]
        )

    op.create_table(
        "fermentation_measurements",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_instance_id",
            uuid,
            sa.ForeignKey("fermentation_stage_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("measurement_type", sa.String(40), nullable=False),
        sa.Column("raw_value", sa.Numeric(12, 6), nullable=False),
        sa.Column("raw_unit", sa.String(16), nullable=False),
        sa.Column("canonical_value", sa.Numeric(12, 6), nullable=False),
        sa.Column("canonical_unit", sa.String(16), nullable=False),
        sa.Column("conversion_model_id", sa.String(80)),
        sa.Column("observed_at", timestamp, nullable=False),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("instrument_reference", sa.String(160)),
        sa.Column("confidence", sa.String(24)),
        sa.Column("note", sa.Text()),
        sa.Column("method", sa.String(32)),
        sa.Column("sample_temperature_c", sa.Numeric(6, 2)),
        sa.Column("validation_status", sa.String(24), server_default="ACCEPTED", nullable=False),
        sa.Column("late_entry", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("late_entry_reason", sa.Text()),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-measurement-v1",
            nullable=False,
        ),
        sa.Column("available_at_original_session_completion", sa.Boolean()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "fermentation_session_id", name="uq_fermentation_measurement_session"),
        sa.ForeignKeyConstraint(
            ["stage_instance_id", "fermentation_session_id"],
            ["fermentation_stage_instances.id", "fermentation_stage_instances.fermentation_session_id"],
            name="fk_fermentation_measurement_stage_session",
        ),
    )
    op.create_index(
        "ix_fermentation_measurements_session_id",
        "fermentation_measurements",
        ["fermentation_session_id"],
    )
    op.create_index(
        "ix_fermentation_measurements_type",
        "fermentation_measurements",
        ["measurement_type"],
    )

    op.create_table(
        "fermentation_measurement_corrections",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_instance_id",
            uuid,
            sa.ForeignKey("fermentation_stage_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("correction_of_id", uuid, nullable=False),
        sa.Column("measurement_type", sa.String(40), nullable=False),
        sa.Column("raw_value", sa.Numeric(12, 6), nullable=False),
        sa.Column("raw_unit", sa.String(16), nullable=False),
        sa.Column("canonical_value", sa.Numeric(12, 6), nullable=False),
        sa.Column("canonical_unit", sa.String(16), nullable=False),
        sa.Column("conversion_model_id", sa.String(80)),
        sa.Column("observed_at", timestamp, nullable=False),
        sa.Column("recorded_at", timestamp, nullable=False),
        sa.Column("actor_user_id", uuid, nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("instrument_reference", sa.String(160)),
        sa.Column("confidence", sa.String(24)),
        sa.Column("note", sa.Text()),
        sa.Column("method", sa.String(32)),
        sa.Column("sample_temperature_c", sa.Numeric(6, 2)),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-measurement-v1",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correction_of_id", name="uq_fermentation_measurement_correction_leaf"),
        sa.UniqueConstraint("id", "fermentation_session_id", name="uq_fermentation_correction_session"),
    )
    op.create_index(
        "ix_fermentation_measurement_corrections_session_id",
        "fermentation_measurement_corrections",
        ["fermentation_session_id"],
    )

    op.create_table(
        "fermentation_derived_gravity_snapshots",
        *common_columns(),
        sa.Column(
            "fermentation_session_id",
            uuid,
            sa.ForeignKey("fermentation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "schema_version",
            sa.String(64),
            server_default="phase4-derived-gravity-v1",
            nullable=False,
        ),
        sa.Column("stable_gravity_status", sa.String(32), nullable=False),
        sa.Column("final_gravity_sg", sa.Numeric(12, 6)),
        sa.Column("apparent_attenuation_ratio", sa.Numeric(8, 6)),
        sa.Column("spread", sa.Numeric(12, 6)),
        sa.Column("window_measurement_ids", sa.JSON(), nullable=False),
        sa.Column("source_measurement_ids", sa.JSON(), nullable=False),
        sa.Column("evaluated_at", timestamp, nullable=False),
        sa.Column("calculation_version", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fermentation_derived_gravity_snapshots_session_id",
        "fermentation_derived_gravity_snapshots",
        ["fermentation_session_id"],
    )


def downgrade() -> None:
    op.drop_table("fermentation_derived_gravity_snapshots")
    op.drop_table("fermentation_measurement_corrections")
    op.drop_table("fermentation_measurements")
    with op.batch_alter_table("fermentation_stage_instances") as batch:
        batch.drop_constraint("uq_fermentation_stage_session", type_="unique")
        batch.drop_column("current_completed_at")
        batch.drop_column("current_activation_started_at")
        batch.drop_column("first_completed_at")
        batch.drop_column("first_started_at")
