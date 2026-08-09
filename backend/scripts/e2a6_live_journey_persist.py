"""Live Epic 2A API journey + PostgreSQL restart row persistence (E2A-6)."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import uuid
import urllib.error
import urllib.request

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://brewingos:brewingos@127.0.0.1:5432/brewingos",
)
# Host-published backend port from docker-compose.
API_BASE = os.environ.get("E2A6_API_BASE", "http://127.0.0.1:8000")


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def api(method: str, path: str, body: dict | None = None) -> dict | list | None:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        raise RuntimeError(f"{method} {path} -> {e.code}: {detail}") from e


async def main() -> int:
    try:
        with urllib.request.urlopen(f"{API_BASE}/health", timeout=5) as resp:
            print("api_health", resp.status)
    except Exception as exc:  # noqa: BLE001
        print("API unreachable at", API_BASE, ":", exc)
        print("Start stack: docker compose up -d postgres backend")
        return 2

    marker = str(uuid.uuid4())[:8]
    brewery = api("GET", "/api/v1/brewery")
    if not brewery:
        brewery = api(
            "POST",
            "/api/v1/brewery",
            {
                "name": f"E2A6 Persist {marker}",
                "preferred_units": "US",
                "timezone": "UTC",
                "default_batch_size": "5",
                "default_batch_size_unit": "gal",
                "default_brewhouse_efficiency": "70",
            },
        )
    assert isinstance(brewery, dict)
    brewery_id = brewery["id"]
    print("brewery_id", brewery_id)

    recipe = api(
        "POST",
        f"/api/v1/breweries/{brewery_id}/recipes",
        {
            "name": f"E2A6 Journey {marker}",
            "style": "American IPA",
            "version": {
                "batch_size": "5",
                "batch_size_unit": "gal",
                "brewhouse_efficiency": "72",
                "boil_time_minutes": 60,
                "mash_method": "SINGLE_INFUSION",
                "intent": {"overall_objective": "E2A6 persistence"},
                "fermentables": [
                    {
                        "ingredient_name": f"2-Row {marker}",
                        "amount": "10",
                        "unit": "lb",
                        "potential_sg": "1.037",
                        "color_lovibond": "2",
                    }
                ],
                "hops": [
                    {
                        "ingredient_name": f"Citra {marker}",
                        "amount": "1",
                        "unit": "oz",
                        "alpha_acid": "12",
                        "stage": "BOIL",
                        "time_minutes": 60,
                    }
                ],
                "yeasts": [
                    {
                        "ingredient_name": f"US-05 {marker}",
                        "expected_attenuation": "78",
                    }
                ],
                "mash_steps": [
                    {
                        "step_name": "Saccharification",
                        "target_temperature_c": "67",
                        "duration_minutes": 60,
                    }
                ],
            },
        },
    )
    assert isinstance(recipe, dict)
    version_id = recipe["current_version"]["id"]
    api("POST", f"/api/v1/recipe-versions/{version_id}/activate", {})
    readiness = api("POST", f"/api/v1/recipe-versions/{version_id}/readiness", {})
    assert isinstance(readiness, dict)
    plan_body: dict = {"client_submission_id": f"plan-{marker}"}
    if readiness.get("overall") in ("YELLOW", "RED"):
        plan_body["readiness_acknowledgement"] = {
            "acknowledged": True,
            "note": "e2a6 persistence journey",
        }
    plan = api("POST", f"/api/v1/recipe-versions/{version_id}/brew-plans", plan_body)
    assert isinstance(plan, dict)
    session = api(
        "POST",
        f"/api/v1/brew-plans/{plan['id']}/sessions",
        {"client_submission_id": f"sess-{marker}"},
    )
    assert isinstance(session, dict)
    sid = session["id"]
    version = session["version"]

    def transition(command: str, **extra) -> dict:
        nonlocal version
        body = {
            "client_submission_id": f"{command.lower()}-{uuid.uuid4()}",
            "expected_session_version": version,
            "command": command,
            **extra,
        }
        out = api("POST", f"/api/v1/brew-sessions/{sid}/transitions", body)
        assert isinstance(out, dict)
        version = out["version"]
        return out

    transition("START_SESSION")
    timers = api(
        "POST",
        f"/api/v1/brew-sessions/{sid}/timers",
        {
            "client_submission_id": f"timer-{marker}",
            "expected_session_version": version,
            "label": "persist-timer",
            "target_duration_seconds": 1,
        },
    )
    assert isinstance(timers, dict)
    version = timers["session_version"]
    timer_id = timers["timer"]["id"]

    for _ in range(20):
        sess = api("GET", f"/api/v1/brew-sessions/{sid}")
        assert isinstance(sess, dict)
        version = sess["version"]
        if sess["status"] != "IN_PROGRESS":
            break
        if sess.get("current_stage_code") == "BREW_DAY_AUDIT":
            break
        try:
            transition("ADVANCE_STAGE")
        except RuntimeError:
            transition("SKIP_STAGE", skip_reason="e2a6 journey skip")

    reqs = api("GET", f"/api/v1/brew-sessions/{sid}/requirements")
    assert isinstance(reqs, list)
    for req in reqs:
        if req["requirement_level"] == "REQUIRED" and req["status"] == "PENDING":
            if req["measurement_code"] == "OG":
                cap = api(
                    "POST",
                    f"/api/v1/brew-sessions/{sid}/measurements",
                    {
                        "client_submission_id": f"og-{marker}",
                        "expected_session_version": version,
                        "requirement_id": req["id"],
                        "raw_value": "1.092",
                        "raw_unit": "SG",
                        "confidence": "HIGH",
                    },
                )
                assert isinstance(cap, dict)
                version = cap["session_version"]
                print(
                    "captured_unusual_og",
                    (cap.get("record") or {}).get("validation_class"),
                )
            else:
                miss = api(
                    "POST",
                    f"/api/v1/measurement-requirements/{req['id']}/miss",
                    {
                        "client_submission_id": f"miss-{req['measurement_code']}-{marker}",
                        "expected_session_version": version,
                        "reason": "e2a6 journey",
                    },
                )
                assert isinstance(miss, dict)
                version = miss["session_version"]

    time.sleep(1.2)
    try:
        obs = api(
            "POST",
            f"/api/v1/timers/{timer_id}/observe-elapsed",
            {
                "client_submission_id": f"obs-{marker}",
                "expected_session_version": version,
            },
        )
        assert isinstance(obs, dict)
        version = obs["session_version"]
    except RuntimeError as exc:
        print("observe_elapsed_note", exc)

    report = api("GET", f"/api/v1/brew-sessions/{sid}/report")
    assert isinstance(report, dict)
    assert report.get("overall_brew_score") is None
    transition("CLOSE_SESSION")
    handoff = api(
        "POST",
        f"/api/v1/brew-sessions/{sid}/fermentation-handoff",
        {
            "client_submission_id": f"handoff-{marker}",
            "expected_session_version": version,
        },
    )
    assert isinstance(handoff, dict)
    assert handoff["session_status"] == "HANDED_OFF"
    print("session_id", sid)
    print("timer_id", timer_id)
    print("handoff_id", handoff["handoff"]["id"])

    # Prefer docker network URL after restart when script runs on host against published ports.
    # Compose postgres is not published by default — connect via temporary backend container.
    _run(["docker", "compose", "restart", "postgres"])
    for i in range(40):
        try:
            probe = subprocess.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "postgres",
                    "pg_isready",
                    "-U",
                    "brewingos",
                    "-d",
                    "brewingos",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        print("Postgres did not become ready after restart")
        return 3

    # Verify rows via backend one-off Python in compose network.
    verify_py = f"""
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    e = create_async_engine(os.environ['DATABASE_URL'])
    async with e.connect() as c:
        status = (await c.execute(text("SELECT status FROM brew_sessions WHERE id='{sid}'"))).scalar()
        events = (await c.execute(text("SELECT count(*) FROM brew_events WHERE brew_session_id='{sid}'"))).scalar()
        timers = (await c.execute(text("SELECT count(*) FROM brew_timers WHERE brew_session_id='{sid}'"))).scalar()
        handoffs = (await c.execute(text("SELECT count(*) FROM fermentation_handoffs WHERE brew_session_id='{sid}'"))).scalar()
        hist = (await c.execute(text('''
            SELECT count(*) FROM measurement_observation_history h
            JOIN measurement_requirements r ON r.id = h.requirement_id
            WHERE r.brew_session_id='{sid}'
        '''))).scalar()
        print('after_restart_status', status)
        print('after_restart_events', events)
        print('after_restart_obs_history', hist)
        print('after_restart_timers', timers)
        print('after_restart_handoffs', handoffs)
        assert status == 'HANDED_OFF'
        assert events >= 1
        assert timers >= 1
        assert handoffs == 1
    await e.dispose()
asyncio.run(main())
"""
    subprocess.check_call(
        [
            "docker",
            "compose",
            "run",
            "--rm",
            "--entrypoint",
            "python",
            "backend",
            "-c",
            verify_py,
        ]
    )

    sess2 = api("GET", f"/api/v1/brew-sessions/{sid}")
    report2 = api("GET", f"/api/v1/brew-sessions/{sid}/report")
    assert isinstance(sess2, dict) and sess2["status"] == "HANDED_OFF"
    assert isinstance(report2, dict) and report2["overall_brew_score"] is None
    print("E2A6_PERSISTENCE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
