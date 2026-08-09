"""Canonical brew_events + E2A-1 PLAN_CREATED / READINESS_ACKNOWLEDGED backfill.

Revision ID: 006
Revises: 005
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brew_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brewery_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("brew_plan_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("brew_session_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("client_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("client_submission_id", sa.String(length=128), nullable=True),
        sa.Column("correlation_key", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "brew_plan_id IS NOT NULL OR brew_session_id IS NOT NULL",
            name="ck_brew_events_plan_or_session",
        ),
        sa.ForeignKeyConstraint(["brewery_id"], ["breweries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brew_plan_id"], ["brew_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_brew_events_session_occurred",
        "brew_events",
        ["brew_session_id", "occurred_at"],
    )
    op.create_index(
        "ix_brew_events_plan_occurred",
        "brew_events",
        ["brew_plan_id", "occurred_at"],
    )
    op.create_index(
        "ix_brew_events_brewery_occurred",
        "brew_events",
        ["brewery_id", "occurred_at"],
    )
    op.create_index(
        "ix_brew_events_type_occurred",
        "brew_events",
        ["event_type", "occurred_at"],
    )
    # Duplicate-safe backfill / retry guard (NULL correlation_key allowed for live events).
    op.create_index(
        "uq_brew_events_correlation_key",
        "brew_events",
        ["correlation_key"],
        unique=True,
        postgresql_where=sa.text("correlation_key IS NOT NULL"),
    )

    # Deterministic E2A-1 backfill: PLAN_CREATED for every brew plan.
    op.execute(
        """
        INSERT INTO brew_events (
            id,
            brewery_id,
            brew_plan_id,
            brew_session_id,
            event_type,
            actor_id,
            occurred_at,
            client_occurred_at,
            payload,
            client_submission_id,
            correlation_key
        )
        SELECT
            gen_random_uuid(),
            bp.brewery_id,
            bp.id,
            NULL,
            'PLAN_CREATED',
            COALESCE(ae.actor_id, bp.created_by),
            COALESCE(ae.occurred_at, bp.created_at),
            NULL,
            jsonb_build_object(
                'brew_plan_id', bp.id,
                'recipe_version_id', bp.recipe_version_id,
                'recipe_id', bp.recipe_id,
                'readiness_status', bp.readiness_status,
                'source', 'e2a1_backfill'
            ),
            NULL,
            'backfill:PLAN_CREATED:' || bp.id::text
        FROM brew_plans bp
        LEFT JOIN LATERAL (
            SELECT a.actor_id, a.occurred_at
            FROM audit_events a
            WHERE a.entity_type = 'BrewPlan'
              AND a.entity_id = bp.id::text
              AND a.action = 'PLAN_CREATED'
            ORDER BY a.occurred_at ASC
            LIMIT 1
        ) ae ON TRUE
        ON CONFLICT (correlation_key) WHERE correlation_key IS NOT NULL DO NOTHING
        """
    )

    # READINESS_ACKNOWLEDGED when plan acknowledged or audit evidence exists.
    op.execute(
        """
        INSERT INTO brew_events (
            id,
            brewery_id,
            brew_plan_id,
            brew_session_id,
            event_type,
            actor_id,
            occurred_at,
            client_occurred_at,
            payload,
            client_submission_id,
            correlation_key
        )
        SELECT
            gen_random_uuid(),
            bp.brewery_id,
            bp.id,
            NULL,
            'READINESS_ACKNOWLEDGED',
            COALESCE(ae.actor_id, bp.readiness_acknowledged_by, bp.created_by),
            COALESCE(ae.occurred_at, bp.readiness_acknowledged_at, bp.created_at),
            NULL,
            jsonb_build_object(
                'brew_plan_id', bp.id,
                'readiness_status', bp.readiness_status,
                'readiness_summary', bp.readiness_summary,
                'checks', COALESCE(bp.readiness_checks_snapshot, '[]'::jsonb),
                'note', bp.readiness_acknowledgement_note,
                'source', 'e2a1_backfill'
            ),
            NULL,
            'backfill:READINESS_ACKNOWLEDGED:' || bp.id::text
        FROM brew_plans bp
        LEFT JOIN LATERAL (
            SELECT a.actor_id, a.occurred_at
            FROM audit_events a
            WHERE a.entity_type = 'BrewPlan'
              AND a.entity_id = bp.id::text
              AND a.action = 'READINESS_ACKNOWLEDGED'
            ORDER BY a.occurred_at ASC
            LIMIT 1
        ) ae ON TRUE
        WHERE bp.readiness_acknowledged = TRUE
           OR ae.actor_id IS NOT NULL
        ON CONFLICT (correlation_key) WHERE correlation_key IS NOT NULL DO NOTHING
        """
    )

    op.execute(
        "UPDATE app_meta SET value = '6', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '006', updated_at = now() WHERE key = 'schema_version'"
    )


def downgrade() -> None:
    op.drop_index("uq_brew_events_correlation_key", table_name="brew_events")
    op.drop_index("ix_brew_events_type_occurred", table_name="brew_events")
    op.drop_index("ix_brew_events_brewery_occurred", table_name="brew_events")
    op.drop_index("ix_brew_events_plan_occurred", table_name="brew_events")
    op.drop_index("ix_brew_events_session_occurred", table_name="brew_events")
    op.drop_table("brew_events")
    op.execute(
        "UPDATE app_meta SET value = '5', updated_at = now() WHERE key = 'increment'"
    )
    op.execute(
        "UPDATE app_meta SET value = '005', updated_at = now() WHERE key = 'schema_version'"
    )
