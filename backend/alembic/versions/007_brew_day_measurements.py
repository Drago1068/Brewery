"""Brew day measurement tables (E2A-3 / ADR-005).

Revision ID: 007
Revises: 006
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Conservative U1 seed: ranges left NULL unless not inventing scientific authority.
_SEED_DEFINITIONS = [
    ("MASH_TEMP", "Mash temperature", "C", "MASH", "REQUIRED", None, None, "Infusion mash temperature"),
    ("MASH_PH", "Mash pH", "pH", "MASH", "RECOMMENDED", None, None, "Mash pH observation"),
    ("PRE_BOIL_VOLUME", "Pre-boil volume", "L", "BOIL", "REQUIRED", None, None, "Volume before boil"),
    ("PRE_BOIL_GRAVITY", "Pre-boil gravity", "SG", "BOIL", "RECOMMENDED", None, None, "Gravity before boil"),
    ("POST_BOIL_VOLUME", "Post-boil volume", "L", "BOIL", "REQUIRED", None, None, "Volume after boil"),
    ("OG", "Original gravity", "SG", "CHILL_KNOCKOUT", "REQUIRED", None, None, "Wort OG at knockout"),
    ("KNOCKOUT_TEMP", "Knockout temperature", "C", "CHILL_KNOCKOUT", "REQUIRED", None, None, "Temperature at knockout"),
    ("YEAST_PITCH_TEMP", "Yeast pitch temperature", "C", "YEAST_PITCH", "REQUIRED", None, None, "Wort temperature at pitch"),
]


def upgrade() -> None:
    op.create_table(
        "measurement_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("default_unit", sa.String(length=32), nullable=False),
        sa.Column("typical_stage_code", sa.String(length=64), nullable=False),
        sa.Column("default_requirement_level", sa.String(length=32), nullable=False),
        sa.Column("expected_min", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("expected_max", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_measurement_definitions_code"),
    )

    op.create_table(
        "measurement_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brew_session_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("stage_occurrence_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("measurement_definition_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("measurement_code", sa.String(length=64), nullable=False),
        sa.Column("requirement_level", sa.String(length=32), nullable=False),
        sa.Column("planned_value", sa.String(length=64), nullable=True),
        sa.Column("planned_unit", sa.String(length=32), nullable=True),
        sa.Column("planned_kind", sa.String(length=32), nullable=True),
        sa.Column("validation_min", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("validation_max", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["stage_occurrence_id"], ["brew_stage_occurrences.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["measurement_definition_id"],
            ["measurement_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "brew_session_id",
            "measurement_code",
            name="uq_measurement_req_session_code",
        ),
    )
    op.create_index(
        "ix_measurement_requirements_session",
        "measurement_requirements",
        ["brew_session_id"],
    )
    op.create_index(
        "ix_measurement_requirements_stage",
        "measurement_requirements",
        ["stage_occurrence_id"],
    )

    op.create_table(
        "measurement_records",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brew_session_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("raw_value", sa.String(length=64), nullable=False),
        sa.Column("raw_unit", sa.String(length=32), nullable=False),
        sa.Column("corrected_value", sa.String(length=64), nullable=True),
        sa.Column("corrected_unit", sa.String(length=32), nullable=True),
        sa.Column("value_kind", sa.String(length=32), nullable=False, server_default="MEASURED"),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("instrument", sa.String(length=200), nullable=True),
        sa.Column("method", sa.String(length=200), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_class", sa.String(length=32), nullable=True),
        sa.Column("validation_notes", sa.Text(), nullable=True),
        sa.Column("latest_observation_history_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("first_captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_by", sa.String(length=128), nullable=False),
        sa.Column("client_submission_id", sa.String(length=128), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["measurement_requirements.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requirement_id", name="uq_measurement_record_requirement"),
    )
    op.create_index(
        "ix_measurement_records_session",
        "measurement_records",
        ["brew_session_id"],
    )

    op.create_table(
        "measurement_observation_history",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("measurement_record_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("event_class", sa.String(length=32), nullable=False),
        sa.Column("raw_value", sa.String(length=64), nullable=True),
        sa.Column("raw_unit", sa.String(length=32), nullable=True),
        sa.Column("corrected_value", sa.String(length=64), nullable=True),
        sa.Column("corrected_unit", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("instrument", sa.String(length=200), nullable=True),
        sa.Column("method", sa.String(length=200), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_class", sa.String(length=32), nullable=True),
        sa.Column("validation_notes", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("client_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_submission_id", sa.String(length=128), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["measurement_requirements.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["measurement_record_id"], ["measurement_records.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_measurement_obs_history_requirement",
        "measurement_observation_history",
        ["requirement_id", "occurred_at"],
    )
    op.create_index(
        "ix_measurement_obs_history_record",
        "measurement_observation_history",
        ["measurement_record_id", "occurred_at"],
    )

    op.create_table(
        "measurement_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("source_command", sa.String(length=64), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("client_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_submission_id", sa.String(length=128), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["measurement_requirements.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_measurement_status_history_requirement",
        "measurement_status_history",
        ["requirement_id", "occurred_at"],
    )

    # FK from records.latest_observation_history_id after history table exists.
    op.create_foreign_key(
        "fk_measurement_records_latest_obs",
        "measurement_records",
        "measurement_observation_history",
        ["latest_observation_history_id"],
        ["id"],
        ondelete="SET NULL",
    )

    for code, name, unit, stage, level, vmin, vmax, desc in _SEED_DEFINITIONS:
        op.execute(
            sa.text(
                """
                INSERT INTO measurement_definitions (
                    id, code, display_name, default_unit, typical_stage_code,
                    default_requirement_level, expected_min, expected_max, description, is_active
                ) VALUES (
                    gen_random_uuid(), :code, :name, :unit, :stage,
                    :level, :vmin, :vmax, :desc, true
                )
                """
            ).bindparams(
                code=code,
                name=name,
                unit=unit,
                stage=stage,
                level=level,
                vmin=vmin,
                vmax=vmax,
                desc=desc,
            )
        )

    op.execute(
        "UPDATE app_meta SET value = '7', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '007', updated_at = now() WHERE key = 'schema_version'"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_measurement_records_latest_obs", "measurement_records", type_="foreignkey"
    )
    op.drop_index(
        "ix_measurement_status_history_requirement",
        table_name="measurement_status_history",
    )
    op.drop_table("measurement_status_history")
    op.drop_index(
        "ix_measurement_obs_history_record",
        table_name="measurement_observation_history",
    )
    op.drop_index(
        "ix_measurement_obs_history_requirement",
        table_name="measurement_observation_history",
    )
    op.drop_table("measurement_observation_history")
    op.drop_index("ix_measurement_records_session", table_name="measurement_records")
    op.drop_table("measurement_records")
    op.drop_index("ix_measurement_requirements_stage", table_name="measurement_requirements")
    op.drop_index("ix_measurement_requirements_session", table_name="measurement_requirements")
    op.drop_table("measurement_requirements")
    op.drop_table("measurement_definitions")
    op.execute(
        "UPDATE app_meta SET value = '6', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '006', updated_at = now() WHERE key = 'schema_version'"
    )
