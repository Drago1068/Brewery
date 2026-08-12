"""Phase 1 and Phase 1A authoritative schema.

Revision ID: 0001_phase1a
Revises:
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_phase1a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid = sa.Uuid()
utc_timestamp = sa.DateTime(timezone=True)


def id_and_created() -> list[sa.Column]:
    return [
        sa.Column("id", uuid, nullable=False),
        sa.Column("created_at", utc_timestamp, nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        *id_and_created(),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "auth_sessions",
        *id_and_created(),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", utc_timestamp, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"])

    op.create_table(
        "recipes",
        *id_and_created(),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipes_owner_id", "recipes", ["owner_id"])

    op.create_table(
        "recipe_versions",
        *id_and_created(),
        sa.Column("recipe_id", uuid, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("target_mash_temperature", sa.Numeric(6, 2), nullable=False),
        sa.Column("mash_temperature_unit", sa.String(16), nullable=False),
        sa.Column("target_mash_ph", sa.Numeric(4, 2), nullable=False),
        sa.Column("mash_ph_tolerance", sa.Numeric(4, 2), nullable=False),
        sa.Column("target_mash_gravity", sa.Numeric(5, 3), nullable=False),
        sa.Column("mash_gravity_tolerance", sa.Numeric(5, 3), nullable=False),
        sa.Column("planned_mash_duration_minutes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_id", "version_number"),
    )
    op.create_index("ix_recipe_versions_recipe_id", "recipe_versions", ["recipe_id"])

    op.create_table(
        "brew_sessions",
        *id_and_created(),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("recipe_version_id", uuid, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", utc_timestamp),
        sa.Column("completed_at", utc_timestamp),
        sa.Column("target_mash_temperature", sa.Numeric(6, 2), nullable=False),
        sa.Column("mash_temperature_unit", sa.String(16), nullable=False),
        sa.Column("target_mash_ph", sa.Numeric(4, 2), nullable=False),
        sa.Column("mash_ph_tolerance", sa.Numeric(4, 2), nullable=False),
        sa.Column("target_mash_gravity", sa.Numeric(5, 3), nullable=False),
        sa.Column("mash_gravity_tolerance", sa.Numeric(5, 3), nullable=False),
        sa.Column("planned_mash_duration_minutes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_brew_sessions_user_id", "brew_sessions", ["user_id"])
    op.create_index("ix_brew_sessions_recipe_version_id", "brew_sessions", ["recipe_version_id"])

    op.create_table(
        "brew_stages",
        *id_and_created(),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", utc_timestamp),
        sa.Column("completed_at", utc_timestamp),
        sa.Column("target_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("target_temperature", sa.Numeric(6, 2), nullable=False),
        sa.Column("temperature_unit", sa.String(16), nullable=False),
        sa.Column("target_ph", sa.Numeric(4, 2), nullable=False),
        sa.Column("ph_tolerance", sa.Numeric(4, 2), nullable=False),
        sa.Column("target_gravity", sa.Numeric(5, 3), nullable=False),
        sa.Column("gravity_tolerance", sa.Numeric(5, 3), nullable=False),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brew_session_id", "name"),
    )
    op.create_index("ix_brew_stages_brew_session_id", "brew_stages", ["brew_session_id"])

    op.create_table(
        "brew_timers",
        *id_and_created(),
        sa.Column("brew_stage_id", uuid, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", utc_timestamp, nullable=False),
        sa.Column("planned_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("paused_at", utc_timestamp),
        sa.Column("accumulated_pause_seconds", sa.Integer(), nullable=False),
        sa.Column("completed_at", utc_timestamp),
        sa.ForeignKeyConstraint(["brew_stage_id"], ["brew_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brew_stage_id", "name"),
    )
    op.create_index("ix_brew_timers_brew_stage_id", "brew_timers", ["brew_stage_id"])

    op.create_table(
        "measurements",
        *id_and_created(),
        sa.Column("brew_stage_id", uuid, nullable=False),
        sa.Column("measurement_type", sa.String(40), nullable=False),
        sa.Column("value", sa.Numeric(8, 3), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("measured_at", utc_timestamp, nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("instrument", sa.String(160)),
        sa.Column("provenance", sa.String(40), nullable=False),
        sa.Column("correction_of_id", uuid),
        sa.ForeignKeyConstraint(["brew_stage_id"], ["brew_stages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["correction_of_id"], ["measurements.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_measurements_brew_stage_id", "measurements", ["brew_stage_id"])
    op.create_index("ix_measurements_measurement_type", "measurements", ["measurement_type"])
    op.create_index("ix_measurements_correction_of_id", "measurements", ["correction_of_id"])

    op.create_table(
        "deviations",
        *id_and_created(),
        sa.Column("measurement_id", uuid, nullable=False),
        sa.Column("target_value", sa.Numeric(8, 3), nullable=False),
        sa.Column("actual_value", sa.Numeric(8, 3), nullable=False),
        sa.Column("variance", sa.Numeric(8, 3), nullable=False),
        sa.Column("tolerance", sa.Numeric(8, 3), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.ForeignKeyConstraint(["measurement_id"], ["measurements.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("measurement_id"),
    )

    op.create_table(
        "brew_journal_events",
        *id_and_created(),
        sa.Column("brew_session_id", uuid, nullable=False),
        sa.Column("brew_stage_id", uuid),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["brew_session_id"], ["brew_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brew_stage_id"], ["brew_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_journal_session", "brew_journal_events", ["brew_session_id"])
    op.create_index("ix_journal_stage", "brew_journal_events", ["brew_stage_id"])
    op.create_index("ix_journal_type", "brew_journal_events", ["event_type"])

    op.create_table(
        "audit_events",
        *id_and_created(),
        sa.Column("actor_user_id", uuid),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", uuid),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_actor", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_action", "audit_events", ["action"])
    op.create_index("ix_audit_entity", "audit_events", ["entity_id"])

    op.create_table(
        "notifications",
        *id_and_created(),
        sa.Column("brew_stage_id", uuid, nullable=False),
        sa.Column("notification_type", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("due_at", utc_timestamp, nullable=False),
        sa.Column("acknowledged_at", utc_timestamp),
        sa.ForeignKeyConstraint(["brew_stage_id"], ["brew_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brew_stage_id", "notification_type"),
    )
    op.create_index("ix_notifications_stage", "notifications", ["brew_stage_id"])

    op.execute(
        """
        CREATE FUNCTION protect_used_recipe_version() RETURNS trigger AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM brew_sessions WHERE recipe_version_id = OLD.id) THEN
            RAISE EXCEPTION 'RecipeVersion used by a brew session is immutable';
          END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER recipe_version_immutable
        BEFORE UPDATE OR DELETE ON recipe_versions
        FOR EACH ROW EXECUTE FUNCTION protect_used_recipe_version();
        """
    )
    op.execute(
        """
        CREATE FUNCTION protect_completed_measurement() RETURNS trigger AS $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM brew_stages
            WHERE id = OLD.brew_stage_id AND status = 'COMPLETED'
          ) THEN
            RAISE EXCEPTION 'Completed brew measurements are immutable; append a correction';
          END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER measurement_completed_immutable
        BEFORE UPDATE OR DELETE ON measurements
        FOR EACH ROW EXECUTE FUNCTION protect_completed_measurement();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS measurement_completed_immutable ON measurements")
    op.execute("DROP FUNCTION IF EXISTS protect_completed_measurement")
    op.execute("DROP TRIGGER IF EXISTS recipe_version_immutable ON recipe_versions")
    op.execute("DROP FUNCTION IF EXISTS protect_used_recipe_version")
    for table in [
        "notifications",
        "audit_events",
        "brew_journal_events",
        "deviations",
        "measurements",
        "brew_timers",
        "brew_stages",
        "brew_sessions",
        "recipe_versions",
        "recipes",
        "auth_sessions",
        "users",
    ]:
        op.drop_table(table)
