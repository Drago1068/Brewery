"""Migration 009 fermentation_handoffs structure guards."""

from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def test_migration_009_chain_and_table():
    path = VERSIONS / "009_fermentation_handoffs.py"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert 'revision: str = "009"' in text
    assert 'down_revision: Union[str, None] = "008"' in text
    assert "fermentation_handoffs" in text
    assert "uq_fermentation_handoffs_brew_session_id" in text
    assert "payload" in text
    assert "FermentationSession" not in text
    assert "UPDATE app_meta SET value = '9'" in text
    assert "UPDATE app_meta SET value = '009'" in text
    assert "UPDATE app_meta SET value = '8'" in text
    assert "UPDATE app_meta SET value = '008'" in text


def test_migrations_005_008_untouched_by_handoff():
    for name in (
        "005_brew_day_plans_sessions.py",
        "006_brew_day_events_stage_machine.py",
        "007_brew_day_measurements.py",
        "008_brew_day_timers.py",
    ):
        text = (VERSIONS / name).read_text(encoding="utf-8")
        assert "fermentation_handoffs" not in text
