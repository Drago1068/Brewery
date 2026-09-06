"""Shared helpers for Phase 4 final-acceptance campaigns (verification-only)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from brewing_api.main import app
from brewing_api.platform.database import SessionLocal


def fresh_authenticated_client(username: str = "brewer", password: str | None = None) -> TestClient:
    """New TestClient simulating API process restart / new connection."""
    password = password or os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "test-password-not-a-secret")
    client = TestClient(app)
    client.headers["Origin"] = "http://testserver"
    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    return client


def utc_iso(dt: datetime | None = None) -> str:
    value = dt or datetime.now(timezone.utc)
    return value.isoformat()


def record_temperature(client: TestClient, session_id: str, stage_id: str, revision: int, value: str = "18.5") -> dict:
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_TEMPERATURE",
            "value": value,
            "unit": "degC",
            "method": "PROBE",
            "observed_at": utc_iso(),
            "stage_instance_id": stage_id,
            "expected_revision": revision,
            "source": "OBSERVED",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
