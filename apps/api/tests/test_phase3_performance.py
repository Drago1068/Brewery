from brewing_api.application.phase3.performance import (
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
    report = run_isolated_performance_harness(samples=12, warmup=2)
    assert report["rule_version"] == "phase3-performance-v1"
    assert report["all_pass"] is True
    assert report["sample_size"] == 12
    for name, item in report["results"].items():
        assert item["status"] == "PASS"
        if name in THRESHOLDS_MS:
            assert item["p95_ms"] <= item["threshold_ms"]
            assert item["count"] == 12


def test_metrics_phase3_returns_operations_and_counters(authenticated_client):
    response = authenticated_client.get("/api/v1/metrics/phase3")
    assert response.status_code == 200
    body = response.json()
    assert "operations" in body
    assert "counters" in body
    assert "sample_count" in body
    assert isinstance(body["operations"], dict)
    assert isinstance(body["counters"], dict)
