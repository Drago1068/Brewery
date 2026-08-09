"""Brew day plans, sessions, stage occurrences, actions, and idempotency ledger.

Revision ID: 005
Revises: 004
Create Date: 2026-08-09

E2A-1 additive migration. Does not create brew event or measurement tables.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brew_plans",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("recipe_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="CREATED"),
        sa.Column("batch_size", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("batch_size_unit", sa.String(length=8), nullable=False),
        sa.Column("brewhouse_efficiency", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("equipment_profile_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("equipment_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recipe_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "planned_calculation_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("readiness_status", sa.String(length=16), nullable=False),
        sa.Column("readiness_summary", sa.Text(), nullable=False),
        sa.Column("readiness_checks_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("readiness_acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("readiness_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("readiness_acknowledged_by", sa.String(length=128), nullable=True),
        sa.Column("readiness_acknowledgement_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brewery_id"], ["breweries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["equipment_profile_id"], ["equipment_profiles.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_brew_plans_brewery_id", "brew_plans", ["brewery_id"])
    op.create_index("ix_brew_plans_recipe_version_id", "brew_plans", ["recipe_version_id"])

    op.create_table(
        "brew_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brew_plan_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PLANNED"),
        sa.Column("current_stage_code", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abort_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brew_plan_id"], ["brew_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brewery_id"], ["breweries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brew_plan_id", name="uq_brew_sessions_brew_plan_id"),
    )
    op.create_index("ix_brew_sessions_brewery_id", "brew_sessions", ["brewery_id"])

    op.create_table(
        "brew_stage_occurrences",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brew_session_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("stage_code", sa.String(length=64), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "brew_session_id",
            "stage_code",
            name="uq_brew_stage_session_code",
        ),
        sa.UniqueConstraint(
            "brew_session_id",
            "sequence_no",
            name="uq_brew_stage_session_sequence",
        ),
    )
    op.create_index(
        "ix_brew_stage_occurrences_session_id",
        "brew_stage_occurrences",
        ["brew_session_id"],
    )
    # At most one ACTIVE stage per session (Epic 2A invariant).
    op.create_index(
        "uq_brew_stage_one_active_per_session",
        "brew_stage_occurrences",
        ["brew_session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "brew_actions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brew_stage_occurrence_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["brew_stage_occurrence_id"],
            ["brew_stage_occurrences.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_brew_actions_stage_occurrence_id",
        "brew_actions",
        ["brew_stage_occurrence_id"],
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("scope_type", sa.String(length=64), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("client_submission_id", sa.String(length=128), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("response_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("session_version_before", sa.Integer(), nullable=True),
        sa.Column("session_version_after", sa.Integer(), nullable=True),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope_type",
            "scope_id",
            "client_submission_id",
            name="uq_idempotency_scope_submission",
        ),
    )
    op.create_index(
        "ix_idempotency_records_scope",
        "idempotency_records",
        ["scope_type", "scope_id"],
    )

    op.execute(
        "UPDATE app_meta SET value = '5', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '005', updated_at = now() WHERE key = 'schema_version'"
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_records_scope", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("ix_brew_actions_stage_occurrence_id", table_name="brew_actions")
    op.drop_table("brew_actions")
    op.drop_index(
        "uq_brew_stage_one_active_per_session",
        table_name="brew_stage_occurrences",
    )
    op.drop_index("ix_brew_stage_occurrences_session_id", table_name="brew_stage_occurrences")
    op.drop_table("brew_stage_occurrences")
    op.drop_index("ix_brew_sessions_brewery_id", table_name="brew_sessions")
    op.drop_table("brew_sessions")
    op.drop_index("ix_brew_plans_recipe_version_id", table_name="brew_plans")
    op.drop_index("ix_brew_plans_brewery_id", table_name="brew_plans")
    op.drop_table("brew_plans")
    op.execute(
        "UPDATE app_meta SET value = '4', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '004', updated_at = now() WHERE key = 'schema_version'"
    )
