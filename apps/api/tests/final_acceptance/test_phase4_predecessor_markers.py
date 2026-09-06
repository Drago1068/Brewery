"""Phase 4 predecessor regression markers for FAO FR-084 / FR-085 / FR-087."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]


def test_fa_fr084_phase3_named_suites_present():
    """P4-FR-084 — Phase 3 named suites remain present for Playwright/API baseline."""
    required = [
        REPO / "tests" / "e2e" / "phase3.spec.ts",
        REPO / "apps" / "api" / "tests" / "test_phase3_backup_restore.py",
        REPO / "apps" / "api" / "tests" / "test_phase3_performance.py",
        REPO / "apps" / "api" / "tests" / "test_phase3_security.py",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    assert not missing, missing


def test_fa_fr085_phase1a_phase2_named_suites_present():
    """P4-FR-085 — Phase 1A / Phase 2 named browser suites remain present."""
    required = [
        REPO / "tests" / "e2e" / "phase1a.spec.ts",
        REPO / "tests" / "e2e" / "phase2.spec.ts",
        REPO / "apps" / "api" / "tests" / "test_phase2_core.py",
        REPO / "apps" / "api" / "tests" / "test_phase2_calculations.py",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    assert not missing, missing


def test_fa_fr087_migration_head_constant_matches_candidate():
    """P4-FR-087 / P4-AC-044 — migration campaign points at Phase 4 journal head."""
    migration = REPO / "apps" / "api" / "tests" / "test_phase4_migration.py"
    text = migration.read_text(encoding="utf-8")
    assert 'EXPECTED_REVISION = "0015_phase4_journal_media_export"' in text
    head_file = (
        REPO
        / "database"
        / "migrations"
        / "versions"
        / "0015_phase4_journal_media_export.py"
    )
    assert head_file.is_file()
