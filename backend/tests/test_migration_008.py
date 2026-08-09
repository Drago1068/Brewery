"""Migration 008 brew_timers structure guards."""

from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def test_migration_008_chain_and_table():
    path = VERSIONS / "008_brew_day_timers.py"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert 'revision: str = "008"' in text
    assert 'down_revision: Union[str, None] = "007"' in text
    assert "brew_timers" in text
    assert "started_at" in text
    assert "ends_at" in text
    assert "elapsed_at" in text
    assert "stopped_at" in text
    assert "cancelled_at" in text
    assert "ck_brew_timers_positive_duration" in text
    assert "fermentation_handoffs" not in text
    assert "celery" not in text.lower()
    assert "redis" not in text.lower()
    assert "UPDATE app_meta SET value = '8'" in text
    assert "UPDATE app_meta SET value = '008'" in text
    # Downgrade restores 007
    assert "UPDATE app_meta SET value = '7'" in text
    assert "UPDATE app_meta SET value = '007'" in text


def test_migrations_005_007_untouched_by_timers():
    for name in (
        "005_brew_day_plans_sessions.py",
        "006_brew_day_events_stage_machine.py",
        "007_brew_day_measurements.py",
    ):
        text = (VERSIONS / name).read_text(encoding="utf-8")
        assert "brew_timers" not in text
