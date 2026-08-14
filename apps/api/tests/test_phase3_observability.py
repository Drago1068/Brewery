def test_metrics_sample_count_increases_after_mutations(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    client.post(f"/api/v1/brew-sessions/{session_id}/pause")
    client.post(f"/api/v1/brew-sessions/{session_id}/resume")
    client.post(
        f"/api/v1/brew-sessions/{session_id}/notes",
        json={"body": "Iodine rest looked complete after stirring."},
    )
    metrics = client.get("/api/v1/metrics/phase3")
    assert metrics.status_code == 200
    body = metrics.json()
    assert body["sample_count"] > 0
    assert body["operations"]
    assert body["counters"]


def test_reconstruct_returns_events_for_correlation_id(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    correlation_id = "phase3-obs-reconstruct-1"
    mutated = client.post(
        f"/api/v1/brew-sessions/{session_id}/notes",
        json={"body": "Noted mash rest for correlation reconstruction."},
        headers={"X-Correlation-ID": correlation_id},
    )
    assert mutated.status_code == 201
    response_id = mutated.headers.get("x-correlation-id") or correlation_id
    reconstructed = client.get(f"/api/v1/metrics/phase3/reconstruct/{response_id}")
    assert reconstructed.status_code == 200
    body = reconstructed.json()
    assert body["correlation_id"] == response_id
    assert isinstance(body["events"], list)
    assert body["events"]
    assert any(item.get("correlation_id") == response_id for item in body["events"])
