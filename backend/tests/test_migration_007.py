"""Migration 007 structure and seed guards."""

from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def test_migration_007_chain_and_tables():
    path = VERSIONS / "007_brew_day_measurements.py"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert 'revision: str = "007"' in text
    assert 'down_revision: Union[str, None] = "006"' in text
    for table in (
        "measurement_definitions",
        "measurement_requirements",
        "measurement_records",
        "measurement_observation_history",
        "measurement_status_history",
    ):
        assert table in text
    assert "MASH_TEMP" in text
    assert "YEAST_PITCH_TEMP" in text
    assert "brew_timers" not in text
    assert "fermentation_handoffs" not in text


def test_seed_leaves_ranges_null():
    text = (VERSIONS / "007_brew_day_measurements.py").read_text(encoding="utf-8")
    # Seed tuples use None for expected_min/max — no invented ranges.
    assert 'None, None, "Infusion mash temperature"' in text or "None, None," in text


def test_migration_007_does_not_include_timers_or_handoffs():
    text = (VERSIONS / "007_brew_day_measurements.py").read_text(encoding="utf-8")
    assert "brew_timers" not in text
    assert "fermentation_handoffs" not in text


def test_008_exists_after_e2a4():
    names = {p.name for p in VERSIONS.glob("*.py")}
    assert any(n.startswith("008") for n in names)
    assert not any(n.startswith("009") for n in names)
