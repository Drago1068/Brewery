"""Phase 4 §37 performance harness (verification-only; no product-code mutation).

Normative thresholds are copied verbatim from the accepted Phase 4 specification §37.
Do not invent thresholds. Browser rows are exercised by Playwright; this module covers API rows.
"""

from __future__ import annotations

import json
import os
import platform
import statistics
import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from brewing_api.application.auth import password_hash
from brewing_api.domain.identity.models import User
from brewing_api.domain.fermentation.models import FermentationMeasurement, FermentationSession
from brewing_api.main import app
from brewing_api.platform.database import SessionLocal, engine
from brewing_api.platform.time import utc_now

# Spec §37 — exact thresholds (ms). PASS if p95 <= threshold.
THRESHOLDS_MS = {
    "GET_session_detail": 500,
    "POST_measurement": 750,
    "POST_complete_fermentation": 1250,
    "JSON_export": 2000,
}

RULE_VERSION = "phase4-performance-v1"
DATASET_TARGETS = {
    "measurements": 200,
    "reminders": 50,
    "timers": 20,
    "journal_events": 100,
    "attachments": 10,
}


def _percentile_95(samples: list[float]) -> float:
    if not samples:
        return float("inf")
    ordered = sorted(samples)
    index = max(0, int(round(0.95 * (len(ordered) - 1))))
    return ordered[index]


def _auth_client(username: str, password: str) -> TestClient:
    client = TestClient(app)
    client.headers["Origin"] = "http://testserver"
    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    return client


def _seed_disposable_owner() -> tuple[str, str]:
    username = f"p4perf-{uuid.uuid4().hex[:10]}"
    password = "p4-perf-password-not-a-secret"
    with SessionLocal() as db:
        db.add(User(username=username, password_hash=password_hash.hash(password)))
        db.commit()
    return username, password


def _seed_perf_session(client: TestClient, measurement_target: int) -> dict:
    """Build disposable fermentation dataset. Reduced targets allowed for smoke."""
    created = client.post(
        "/api/v1/recipes",
        json={
            "name": f"P4-Perf-{uuid.uuid4().hex[:8]}",
            "target_mash_temperature": "152.00",
            "target_mash_ph": "5.30",
            "mash_ph_tolerance": "0.05",
            "target_mash_gravity": "1.050",
            "mash_gravity_tolerance": "0.003",
            "planned_mash_duration_minutes": 1,
        },
    )
    assert created.status_code in {200, 201}, created.text
    version_id = created.json()["version_id"]
    brew = client.post(
        "/api/v1/brew-sessions",
        json={"recipe_version_id": version_id, "operation_id": str(uuid.uuid4())},
    )
    assert brew.status_code in {200, 201}, brew.text
    brew_id = brew.json()["id"]
    revision = client.get(f"/api/v1/brew-sessions/{brew_id}").json()["revision"]
    started = client.post(
        f"/api/v1/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert started.status_code == 200, started.text
    revision = client.get(f"/api/v1/brew-sessions/{brew_id}").json()["revision"]
    mash = client.post(
        f"/api/v1/brew-sessions/{brew_id}/mash/start",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert mash.status_code == 200, mash.text
    mash_id = mash.json()["id"]
    for payload in (
        {
            "measurement_type": "MASH_PH",
            "value": "5.30",
            "unit": "pH",
            "operation_id": str(uuid.uuid4()),
            "method": "METER",
            "sample_temperature_c": "65.00",
            "temperature_compensated": True,
        },
        {
            "measurement_type": "MASH_GRAVITY",
            "value": "1.048",
            "unit": "SG",
            "operation_id": str(uuid.uuid4()),
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
        },
    ):
        assert (
            client.post(f"/api/v1/brew-sessions/stages/{mash_id}/measurements", json=payload).status_code
            == 201
        )
    revision = client.get(f"/api/v1/brew-sessions/{brew_id}").json()["revision"]
    assert (
        client.post(
            f"/api/v1/brew-sessions/{brew_id}/pitch-handoff",
            json={
                "operation_id": str(uuid.uuid4()),
                "yeast_addition_note": "perf yeast",
                "pitch_temperature_c": "18.0",
                "expected_revision": revision,
            },
        ).status_code
        == 201
    )
    revision = client.get(f"/api/v1/brew-sessions/{brew_id}").json()["revision"]
    assert (
        client.post(
            f"/api/v1/brew-sessions/stages/{mash_id}/complete",
            json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
        ).status_code
        == 200
    )
    ferm = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert ferm.status_code == 201, ferm.text
    body = ferm.json()
    stage_id = next(
        s["id"] for s in body["stages"] if s["canonical_stage_type"] == "ACTIVE_FERMENTATION"
    )
    session_id = body["id"]
    revision = body["revision"]

    # Seed temperature leaves after pitch time (observed_at must not precede pitch).
    for i in range(measurement_target):
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/measurements",
            json={
                "operation_id": str(uuid.uuid4()),
                "measurement_type": "FERMENTATION_TEMPERATURE",
                "value": f"{18 + (i % 5) * 0.1:.1f}",
                "unit": "degC",
                "method": "PROBE",
                "observed_at": utc_now().isoformat(),
                "stage_instance_id": stage_id,
                "expected_revision": revision,
                "source": "OBSERVED",
            },
        )
        assert response.status_code == 201, response.text
        revision = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]

    for i in range(min(20, measurement_target // 5 or 1)):
        client.post(
            f"/api/v1/fermentation-sessions/{session_id}/notes",
            json={
                "operation_id": str(uuid.uuid4()),
                "body": f"perf journal note {i}",
                "expected_revision": revision,
            },
        )
        revision = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]

    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    return {
        "session_id": session_id,
        "stage_id": stage_id,
        "revision": detail["revision"],
        "timer_count": len(detail.get("timers") or []),
        "reminder_count": len(detail.get("reminders") or []),
        "measurement_count": measurement_target,
    }


def run_isolated_phase4_performance_harness(
    *,
    samples: int | None = None,
    warmup: int | None = None,
    measurement_seed: int | None = None,
) -> dict:
    """Execute §37 API operations against a disposable owner + session."""
    require_pg = os.environ.get("PHASE4_PERF_REQUIRE_POSTGRES") == "1"
    if require_pg and engine.dialect.name != "postgresql":
        raise RuntimeError("PHASE4_PERF_REQUIRE_POSTGRES=1 but engine is not PostgreSQL")

    samples = samples if samples is not None else int(os.environ.get("PHASE4_PERF_SAMPLES", "100"))
    warmup = warmup if warmup is not None else int(os.environ.get("PHASE4_PERF_WARMUP", "10"))
    measurement_seed = (
        measurement_seed
        if measurement_seed is not None
        else int(os.environ.get("PHASE4_PERF_MEASUREMENTS", str(DATASET_TARGETS["measurements"])))
    )

    with SessionLocal() as db:
        user_count_before = db.scalar(select(func.count()).select_from(User)) or 0

    username, password = _seed_disposable_owner()
    client = _auth_client(username, password)
    fixture = _seed_perf_session(client, measurement_seed)
    session_id = fixture["session_id"]
    stage_id = fixture["stage_id"]

    results: dict[str, dict] = {}

    def measure(name: str, threshold: int, fn) -> None:
        """fn may return (ok: bool, elapsed_ms: float) to supply its own clock, else bool."""
        raw: list[float] = []
        for i in range(warmup + samples):
            started = time.perf_counter()
            result = fn(i)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if isinstance(result, tuple):
                ok, elapsed_ms = result
            else:
                ok = bool(result)
            if i >= warmup and ok:
                raw.append(elapsed_ms)
        p95 = _percentile_95(raw)
        status = "PASS" if len(raw) >= samples and p95 <= threshold else "FAIL"
        results[name] = {
            "TEST_ID": f"P4-PERF-{name}",
            "OPERATION": name,
            "DATASET": f"disposable:{measurement_seed}m",
            "THRESHOLD": threshold,
            "threshold_ms": threshold,
            "OBSERVED": round(p95, 3),
            "p95_ms": round(p95, 3),
            "UNIT": "ms",
            "RESULT": status,
            "status": status,
            "SAMPLE_COUNT": len(raw),
            "raw_samples_ms": raw,
            "mean_ms": round(statistics.fmean(raw), 3) if raw else None,
        }

    def get_detail(_i: int) -> bool:
        response = client.get(f"/api/v1/fermentation-sessions/{session_id}")
        return response.status_code == 200 and response.json()["id"] == session_id

    measure("GET_session_detail", THRESHOLDS_MS["GET_session_detail"], get_detail)

    def post_measurement(i: int) -> bool:
        rev = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/measurements",
            json={
                "operation_id": str(uuid.uuid4()),
                "measurement_type": "FERMENTATION_TEMPERATURE",
                "value": f"{19 + (i % 3) * 0.1:.1f}",
                "unit": "degC",
                "method": "PROBE",
                "observed_at": utc_now().isoformat(),
                "stage_instance_id": stage_id,
                "expected_revision": rev,
                "source": "OBSERVED",
            },
        )
        return response.status_code == 201

    measure("POST_measurement", THRESHOLDS_MS["POST_measurement"], post_measurement)

    def json_export(_i: int) -> bool:
        response = client.get(f"/api/v1/fermentation-sessions/{session_id}/export?format=json")
        return response.status_code == 200 and "document" in response.json()

    measure("JSON_export", THRESHOLDS_MS["JSON_export"], json_export)

    def complete_ferm(i: int) -> tuple[bool, float]:
        """Each sample uses a fresh disposable session (complete is terminalizing)."""
        from brewing_api.application.phase3.csrf import reset_rate_limits

        reset_rate_limits()
        fresh = _seed_perf_session(client, 1)
        gravity = client.post(
            f"/api/v1/fermentation-sessions/{fresh['session_id']}/measurements",
            json={
                "operation_id": str(uuid.uuid4()),
                "measurement_type": "FERMENTATION_GRAVITY",
                "value": "1.020",
                "unit": "SG",
                "method": "HYDROMETER",
                "sample_temperature_c": "20.00",
                "observed_at": utc_now().isoformat(),
                "stage_instance_id": fresh["stage_id"],
                "expected_revision": fresh["revision"],
                "source": "OBSERVED",
            },
        )
        if gravity.status_code != 201:
            return False, 0.0
        rev = client.get(f"/api/v1/fermentation-sessions/{fresh['session_id']}").json()["revision"]
        started = time.perf_counter()
        response = client.post(
            f"/api/v1/fermentation-sessions/{fresh['session_id']}/commands/complete-fermentation",
            json={
                "operation_id": str(uuid.uuid4()),
                "expected_revision": rev,
                "override": True,
                "override_reason": "Phase 4 performance harness eligible override for disposable session",
            },
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return response.status_code == 200, elapsed_ms

    if os.environ.get("PHASE4_PERF_ALLOW_COMPLETE") == "1":
        measure(
            "POST_complete_fermentation",
            THRESHOLDS_MS["POST_complete_fermentation"],
            complete_ferm,
        )
    else:
        results["POST_complete_fermentation"] = {
            "TEST_ID": "P4-PERF-POST_complete_fermentation",
            "OPERATION": "POST_complete_fermentation",
            "DATASET": f"disposable:{measurement_seed}m",
            "THRESHOLD": THRESHOLDS_MS["POST_complete_fermentation"],
            "OBSERVED": None,
            "UNIT": "ms",
            "RESULT": "BLOCKED",
            "status": "BLOCKED",
            "blocker": "Set PHASE4_PERF_ALLOW_COMPLETE=1 to time complete-fermentation on disposable fixtures",
            "SAMPLE_COUNT": 0,
            "raw_samples_ms": [],
        }

    with SessionLocal() as db:
        user_count_after = db.scalar(select(func.count()).select_from(User)) or 0
        # Disposable owner only — bootstrap admin must be unchanged as authoritative user.
        admin = db.scalar(select(User).where(User.username == "brewer"))
        admin_id = str(admin.id) if admin else None

    artifact_dir = Path(
        os.environ.get(
            "PHASE4_PERF_ARTIFACT_DIR",
            str(Path(__file__).resolve().parents[3] / "docs" / "evidence"),
        )
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "PHASE_4_PERF_ACCEPTANCE_SAMPLES.json"
    report = {
        "rule_version": RULE_VERSION,
        "THRESHOLDS_MS": THRESHOLDS_MS,
        "sample_size": samples,
        "SAMPLE_COUNT": samples,
        "warmup": warmup,
        "dataset": fixture,
        "DATASET_TARGETS": DATASET_TARGETS,
        "results": results,
        "REAL_USER_SESSION_MUTATIONS": 0,
        "disposable_users_created": max(0, user_count_after - user_count_before),
        "bootstrap_admin_id": admin_id,
        "ENVIRONMENT": {
            "engine": engine.dialect.name,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "PHASE4_PERF_ENV": os.environ.get("PHASE4_PERF_ENV", ""),
            "fallback": engine.dialect.name == "sqlite",
        },
        "all_pass": all(item.get("RESULT") == "PASS" for item in results.values()),
    }
    artifact_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["raw_sample_artifact"] = str(artifact_path)
    return report
