import time

from brewing_api.application.phase3.performance import THRESHOLDS_MS


def _measured_results_pass(report: dict) -> bool:
    if report.get("all_pass") is True:
        return True
    results = report.get("results") or {}
    measured = [item for item in results.values() if item.get("status") != "SKIPPED"]
    return bool(measured) and all(item.get("status") == "PASS" for item in measured)


def test_performance_bench_meets_p95_thresholds(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    details = client.get(f"/api/v1/brew-sessions/{session_id}")
    assert details.status_code == 200
    bench = client.post(f"/api/v1/brew-sessions/{session_id}/performance-bench")
    assert bench.status_code == 200
    body = bench.json()
    assert body["rule_version"] == "phase3-performance-v1"
    assert "results" in body
    assert _measured_results_pass(body)
    for name, item in body["results"].items():
        if item.get("status") == "PASS" and name in THRESHOLDS_MS:
            assert item["p95_ms"] <= item["threshold_ms"]


def test_measurement_plus_reminder_microbench_under_1000ms_p95(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    reminder_id = details["mash"]["notifications"][0]["id"]
    samples: list[float] = []
    for _ in range(6):
        started = time.perf_counter()
        ack = client.post(f"/api/v1/brew-sessions/reminders/{reminder_id}/acknowledge")
        projection = client.get(f"/api/v1/brew-sessions/{session_id}")
        samples.append((time.perf_counter() - started) * 1000)
        assert ack.status_code == 200
        assert ack.json()["status"] == "ACKNOWLEDGED"
        assert projection.status_code == 200
        assert projection.json()["mash"]["notifications"]
    started = time.perf_counter()
    recorded = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/measurements",
        json={"measurement_type": "MASH_PH", "value": "5.30", "unit": "pH"},
    )
    samples.append((time.perf_counter() - started) * 1000)
    assert recorded.status_code == 201
    samples.sort()
    p95 = samples[int(0.95 * (len(samples) - 1))]
    assert p95 <= THRESHOLDS_MS["measurement_plus_reminder"]


def test_metrics_phase3_returns_operations_and_counters(authenticated_client):
    response = authenticated_client.get("/api/v1/metrics/phase3")
    assert response.status_code == 200
    body = response.json()
    assert "operations" in body
    assert "counters" in body
    assert "sample_count" in body
    assert isinstance(body["operations"], dict)
    assert isinstance(body["counters"], dict)
