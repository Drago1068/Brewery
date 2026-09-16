"""Phase 4 §37 performance final-acceptance campaign."""

from __future__ import annotations

import os

import pytest

from brewing_api.platform.database import engine
from final_acceptance.phase4_performance_harness import (
    DATASET_TARGETS,
    THRESHOLDS_MS,
    run_isolated_phase4_performance_harness,
)

pytestmark = pytest.mark.integration


def test_phase4_performance_harness_smoke():
    """Reduced-sample smoke proving harness wiring (not normative §37 acceptance)."""
    report = run_isolated_phase4_performance_harness(
        samples=5,
        warmup=1,
        measurement_seed=12,
    )
    assert report["rule_version"] == "phase4-performance-v1"
    assert report["SAMPLE_COUNT"] == 5
    assert report["REAL_USER_SESSION_MUTATIONS"] == 0
    assert report["disposable_users_created"] >= 1
    for name in ("GET_session_detail", "POST_measurement", "JSON_export"):
        item = report["results"][name]
        assert item["RESULT"] == "PASS", item
        assert item["p95_ms"] <= THRESHOLDS_MS[name]
        assert len(item["raw_samples_ms"]) == 5
    # complete-fermentation remains BLOCKED unless explicitly enabled.
    assert report["results"]["POST_complete_fermentation"]["RESULT"] in {"PASS", "BLOCKED"}


def test_phase4_performance_acceptance_reference_class():
    """Normative P4-FR-081 / P4-AC-041 / P4-ADV-016 gate: ≥100 samples on PostgreSQL."""
    postgres_requested = os.environ.get("TEST_USE_POSTGRES") == "1"
    postgres_required = os.environ.get("PHASE4_PERF_REQUIRE_POSTGRES") == "1"
    if not postgres_requested and not postgres_required:
        pytest.skip(
            "Performance acceptance requires TEST_USE_POSTGRES=1 or PHASE4_PERF_REQUIRE_POSTGRES=1"
        )
    os.environ["PHASE4_PERF_REQUIRE_POSTGRES"] = "1"
    os.environ.setdefault("PHASE4_PERF_ALLOW_COMPLETE", "1")
    report = run_isolated_phase4_performance_harness(samples=100, warmup=10)
    env = report["ENVIRONMENT"]
    assert env.get("fallback") is not True
    assert engine.dialect.name == "postgresql"
    assert report["SAMPLE_COUNT"] == 100
    assert report["dataset"]["measurement_count"] >= DATASET_TARGETS["measurements"]
    assert report["REAL_USER_SESSION_MUTATIONS"] == 0
    for name, threshold in THRESHOLDS_MS.items():
        item = report["results"][name]
        assert item["RESULT"] == "PASS", item
        assert item["OBSERVED"] <= threshold
        assert item["SAMPLE_COUNT"] == 100
    assert report["all_pass"] is True
    assert report.get("raw_sample_artifact")
