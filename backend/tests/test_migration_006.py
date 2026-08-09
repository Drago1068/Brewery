"""Migration 006 structure and backfill algorithm tests."""

from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def test_migration_006_file_and_chain():
    path = VERSIONS / "006_brew_day_events_stage_machine.py"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert 'revision: str = "006"' in text
    assert 'down_revision: Union[str, None] = "005"' in text
    assert "brew_events" in text
    assert "uq_brew_events_correlation_key" in text
    assert "ix_brew_events_session_occurred" in text
    assert "backfill:PLAN_CREATED:" in text
    assert "backfill:READINESS_ACKNOWLEDGED:" in text
    assert "ON CONFLICT" in text
    assert "readiness_acknowledged = TRUE" in text
    assert "COALESCE(ae.occurred_at" in text
    # Does not create measurement/timer tables.
    assert "measurement_requirements" not in text
    assert "brew_timers" not in text
    assert "fermentation_handoffs" not in text


def test_backfill_sql_prefers_audit_evidence_and_skips_green_ack():
    text = (VERSIONS / "006_brew_day_events_stage_machine.py").read_text(encoding="utf-8")
    # GREEN plans without ack must not match the acknowledgement insert predicate alone.
    assert "READINESS_ACKNOWLEDGED" in text
    assert "bp.readiness_acknowledged = TRUE" in text
    assert "ae.actor_id IS NOT NULL" in text
    # Never use migration now() as primary when originals exist.
    assert "COALESCE(ae.occurred_at, bp.created_at)" in text
    assert "COALESCE(ae.occurred_at, bp.readiness_acknowledged_at, bp.created_at)" in text


def test_migration_005_still_present():
    assert (VERSIONS / "005_brew_day_plans_sessions.py").exists()


def test_no_007_measurement_migration_yet():
    names = {p.name for p in VERSIONS.glob("*.py")}
    assert not any(n.startswith("007") for n in names)
    assert not any(n.startswith("008") for n in names)
    assert not any(n.startswith("009") for n in names)
