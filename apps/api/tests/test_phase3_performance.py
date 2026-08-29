import os

import pytest

from brewing_api.application.phase3.performance import (
    REQUIRED_THROUGH_PITCH,
    THRESHOLDS_MS,
    run_isolated_performance_harness,
    session_fingerprint,
)
from brewing_api.platform.database import SessionLocal


def test_performance_bench_route_removed_and_isolated_harness_passes(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    with SessionLocal() as db:
        before = session_fingerprint(db, session_id)
    removed = client.post(f"/api/v1/brew-sessions/{session_id}/performance-bench")
    assert removed.status_code in {404, 405}
    with SessionLocal() as db:
        after = session_fingerprint(db, session_id)
    assert before == after
    # Reduced-sample smoke only. Normative acceptance is
    # test_phase3_performance_acceptance_reference_class (100 samples, PostgreSQL).
    report = run_isolated_performance_harness(samples=12, warmup=2)
    assert report["rule_version"] == "phase3-performance-v1"
    assert report["all_pass"] is True
    assert report["sample_size"] == 12
    assert report["SAMPLE_COUNT"] == 12
    assert report["REAL_USER_SESSION_MUTATIONS"] == 0
    assert report["production_route"] == "ABSENT"
    dataset = report["dataset"]
    assert dataset["canonical_stage_count"] >= 13
    assert dataset["repeated_occurrences"] >= 3
    assert dataset["timers"] >= 10
    assert dataset["reminders"] >= 20
    assert dataset["measurements"] >= 100
    assert dataset["additions"] >= 100
    assert dataset["notes"] >= 50
    assert dataset["attachment_metadata"] >= 20
    assert dataset["journal_events"] >= 750
    for name in REQUIRED_THROUGH_PITCH:
        assert name in dataset["canonical_stages"]
    assert "ENVIRONMENT" in report
    assert "DATASET" in report
    env = report.get("ENVIRONMENT") or report.get("environment") or {}
    if env.get("fallback") or env.get("engine") == "sqlite-memory":
        assert os.environ.get("TEST_USE_POSTGRES") != "1"
        assert os.environ.get("PHASE3_PERF_REQUIRE_POSTGRES") != "1"
    for name, item in report["results"].items():
        assert item["status"] == "PASS"
        assert item["RESULT"] == "PASS"
        if name in THRESHOLDS_MS:
            assert item["p95_ms"] <= item["threshold_ms"]
            assert item["P95"] <= item["THRESHOLD"]
            assert item["count"] == 12
            assert item["SAMPLE_COUNT"] == 12
            assert len(item["raw_samples_ms"]) == 12
    html = report["results"]["journal_html_750"]
    assert html["P95"] <= html["THRESHOLD"]
    assert report.get("raw_sample_artifact")


def test_phase3_performance_acceptance_reference_class():
    """Normative P3-FR-088 / RR-008 gate: 100 server samples on PostgreSQL."""
    postgres_requested = os.environ.get("TEST_USE_POSTGRES") == "1"
    postgres_required = os.environ.get("PHASE3_PERF_REQUIRE_POSTGRES") == "1"
    if not postgres_requested and not postgres_required:
        pytest.skip(
            "Performance acceptance requires TEST_USE_POSTGRES=1 or PHASE3_PERF_REQUIRE_POSTGRES=1"
        )
    os.environ["PHASE3_PERF_REQUIRE_POSTGRES"] = "1"
    report = run_isolated_performance_harness(samples=100, warmup=10)
    env = report.get("ENVIRONMENT") or report.get("environment") or {}
    assert env.get("fallback") is not True
    assert "sqlite" not in str(env.get("engine", "")).lower()
    assert report["all_pass"] is True
    assert report["SAMPLE_COUNT"] == 100
    assert report["sample_size"] == 100
    assert report.get("raw_sample_artifact")
    dataset = report["dataset"]
    assert dataset["canonical_stage_count"] >= 13
    assert dataset["repeated_occurrences"] >= 3
    assert dataset["journal_events"] >= 750
    for name, item in report["results"].items():
        assert item["status"] == "PASS"
        if name in THRESHOLDS_MS:
            assert item["count"] == 100
            assert len(item["raw_samples_ms"]) == 100
            assert item["p95_ms"] <= item["threshold_ms"]


def test_metrics_phase3_returns_operations_and_counters(authenticated_client):
    response = authenticated_client.get("/api/v1/metrics/phase3")
    assert response.status_code == 200
    body = response.json()
    assert "operations" in body
    assert "counters" in body
    assert "sample_count" in body
    assert isinstance(body["operations"], dict)
    assert isinstance(body["counters"], dict)
