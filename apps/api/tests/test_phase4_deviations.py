"""Slice 10 — DEVIATIONS (P4-FR-058 / §22)."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from brewing_api.application.auth import password_hash
from brewing_api.application.phase4.deviations import derived_deviation_identity
from brewing_api.domain.brew_sessions.models import BrewSession
from brewing_api.domain.fermentation.models import (
    FermentationDeviation,
    FermentationJournalEvent,
    FermentationPlanSnapshot,
    FermentationSession,
)
from brewing_api.domain.identity.models import User
from brewing_api.domain.recipes.models import RecipeProcessStep
from brewing_api.main import app
from brewing_api.platform.database import SessionLocal


def _temp_payload(started, *, value: str, observed_offset_minutes: int = 0) -> dict:
    observed = datetime.now(UTC) + timedelta(minutes=observed_offset_minutes)
    return {
        "operation_id": str(uuid.uuid4()),
        "measurement_type": "FERMENTATION_TEMPERATURE",
        "value": value,
        "unit": "degC",
        "observed_at": observed.isoformat(),
        "stage_instance_id": started["active_stage_id"],
        "method": "PROBE",
        "expected_revision": started["fermentation_revision"],
    }


def _set_fermentation_target(
    session_id: str, *, target_c: str = "18.0", tolerance: str = "1.0"
) -> None:
    with SessionLocal() as db:
        snapshot = db.scalar(
            select(FermentationPlanSnapshot).where(
                FermentationPlanSnapshot.fermentation_session_id == uuid.UUID(session_id)
            )
        )
        assert snapshot is not None
        payload = dict(snapshot.payload or {})
        payload["fermentation_temperature_c"] = target_c
        payload["fermentation_temperature_status"] = "SPECIFIED"
        payload["temperature_tolerance_c"] = tolerance
        payload["temperature_tolerance_provenance"] = "TEST_FIXTURE"
        snapshot.payload = payload
        db.commit()


def _refresh_revision(client, session_id: str) -> int:
    body = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    return body["revision"]


def test_fr058_temperature_excursion_derived_identity_and_leaf(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _set_fermentation_target(session_id, target_c="18.0", tolerance="1.0")
    started_fermentation["fermentation_revision"] = _refresh_revision(client, session_id)

    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_temp_payload(started_fermentation, value="22.0"),
    )
    assert response.status_code == 201, response.text
    measurement_id = response.json()["id"]

    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    current = [d for d in detail["deviations"] if d["status"] == "CURRENT"]
    assert len(current) == 1
    row = current[0]
    assert row["deviation_class"] == "TEMPERATURE_EXCURSION"
    assert row["origin"] == "DERIVED"
    assert row["exceeded"] is True
    assert row["source_evidence_id"] == measurement_id
    assert Decimal(row["measured_value"]) == Decimal("22.0")
    assert Decimal(row["target_value"]) == Decimal("18.0")
    assert Decimal(row["tolerance_value"]) == Decimal("1.0")

    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        assert session is not None
        expected = derived_deviation_identity(
            session_id=session.id,
            deviation_class="TEMPERATURE_EXCURSION",
            source_evidence_id=uuid.UUID(measurement_id),
            plan_hash=session.logical_plan_hash or "",
        )
        assert row["derived_identity"] == str(expected)
        events = list(
            db.scalars(
                select(FermentationJournalEvent).where(
                    FermentationJournalEvent.fermentation_session_id == session.id,
                    FermentationJournalEvent.event_type == "FERMENTATION_DEVIATION_RECORDED",
                )
            ).all()
        )
        assert len(events) == 1


def test_fr058_within_tolerance_creates_no_deviation(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _set_fermentation_target(session_id, target_c="18.0", tolerance="1.0")
    started_fermentation["fermentation_revision"] = _refresh_revision(client, session_id)
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_temp_payload(started_fermentation, value="18.5"),
    )
    assert response.status_code == 201, response.text
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert detail["deviations"] == []


def test_fr058_correction_supersedes_prior_leaf(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _set_fermentation_target(session_id, target_c="18.0", tolerance="1.0")
    started_fermentation["fermentation_revision"] = _refresh_revision(client, session_id)

    created = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_temp_payload(started_fermentation, value="22.0"),
    )
    assert created.status_code == 201, created.text
    measurement_id = created.json()["id"]
    revision = _refresh_revision(client, session_id)

    corrected = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{measurement_id}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": measurement_id,
            "value": "18.2",
            "unit": "degC",
            "observed_at": datetime.now(UTC).isoformat(),
            "method": "PROBE",
            "reason": "Instrument misread; corrected temperature observation value",
            "expected_revision": revision,
        },
    )
    assert corrected.status_code == 201, corrected.text

    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    by_status: dict[str, list] = {}
    for item in detail["deviations"]:
        by_status.setdefault(item["status"], []).append(item)
    assert len(by_status.get("SUPERSEDED", [])) == 1
    assert len(by_status.get("CURRENT", [])) == 1
    current = by_status["CURRENT"][0]
    assert current["exceeded"] is False
    assert Decimal(current["measured_value"]) == Decimal("18.2")
    assert current["supersedes_id"] == by_status["SUPERSEDED"][0]["id"]
    assert current["derived_identity"] == by_status["SUPERSEDED"][0]["derived_identity"]


def test_fr058_unspecified_target_no_excursion(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_temp_payload(started_fermentation, value="30.0"),
    )
    assert response.status_code == 201, response.text
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert detail["deviations"] == []


def test_fr058_cross_owner_session_404(started_fermentation, client):
    owner = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _set_fermentation_target(session_id)
    started_fermentation["fermentation_revision"] = _refresh_revision(owner, session_id)
    created = owner.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_temp_payload(started_fermentation, value="25.0"),
    )
    assert created.status_code == 201, created.text

    with SessionLocal() as db:
        db.add(
            User(
                username="slice10-other",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "slice10-other", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    denied = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert denied.status_code == 404


def test_fr058_recovery_reread_deviations(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _set_fermentation_target(session_id)
    started_fermentation["fermentation_revision"] = _refresh_revision(client, session_id)
    created = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_temp_payload(started_fermentation, value="24.0"),
    )
    assert created.status_code == 201, created.text
    expected = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["deviations"]

    with TestClient(app) as fresh:
        fresh.headers["Origin"] = "http://testserver"
        login = fresh.post(
            "/api/v1/auth/login",
            json={"username": "brewer", "password": "test-password-not-a-secret"},
        )
        assert login.status_code == 200
        fresh.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        reread = fresh.get(f"/api/v1/fermentation-sessions/{session_id}")
        assert reread.status_code == 200
        assert reread.json()["deviations"] == expected


def test_fr058_measurement_idempotency_no_duplicate_deviation(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _set_fermentation_target(session_id)
    started_fermentation["fermentation_revision"] = _refresh_revision(client, session_id)
    payload = _temp_payload(started_fermentation, value="23.0")
    first = client.post(f"/api/v1/fermentation-sessions/{session_id}/measurements", json=payload)
    assert first.status_code == 201, first.text
    replay = client.post(f"/api/v1/fermentation-sessions/{session_id}/measurements", json=payload)
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == first.json()["id"]
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(FermentationDeviation).where(
                    FermentationDeviation.fermentation_session_id == uuid.UUID(session_id),
                    FermentationDeviation.deviation_class == "TEMPERATURE_EXCURSION",
                )
            ).all()
        )
        assert len(rows) == 1
        assert rows[0].status == "CURRENT"


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("TEST_USE_POSTGRES") != "1",
    reason="Slice 10 concurrency requires PostgreSQL",
)
def test_fr058_concurrent_temperature_one_current_leaf(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _set_fermentation_target(session_id)
    barrier = threading.Barrier(2)
    results: list[int] = []

    def worker(value: str) -> None:
        barrier.wait()
        revision = _refresh_revision(client, session_id)
        payload = _temp_payload(started_fermentation, value=value)
        payload["expected_revision"] = revision
        payload["operation_id"] = str(uuid.uuid4())
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/measurements",
            json=payload,
        )
        results.append(response.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, "22.0"), pool.submit(worker, "23.0")]
        for future in futures:
            future.result()

    assert 201 in results
    assert 409 in results
    with SessionLocal() as db:
        current = list(
            db.scalars(
                select(FermentationDeviation).where(
                    FermentationDeviation.fermentation_session_id == uuid.UUID(session_id),
                    FermentationDeviation.status == "CURRENT",
                    FermentationDeviation.deviation_class == "TEMPERATURE_EXCURSION",
                )
            ).all()
        )
        assert len(current) == 1


def test_fr058_foundation_schedule_target_used(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    with SessionLocal() as db:
        brew = db.get(BrewSession, uuid.UUID(brew_session_id))
        assert brew is not None
        db.add(
            RecipeProcessStep(
                recipe_version_id=brew.recipe_version_id,
                step_type="FERMENTATION_FOUNDATION",
                sequence=1,
                name="Primary",
                temperature_c=Decimal("19.0"),
                details={
                    "schedule": [
                        {"effective_offset_minutes": 0, "target_temp_c": "19.0"},
                        {"effective_offset_minutes": 60, "target_temp_c": "16.0"},
                    ],
                    "temperature_tolerance_c": "0.5",
                },
            )
        )
        db.commit()

    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201, started.text
    body = started.json()
    session_id = body["id"]
    active = next(
        stage for stage in body["stages"] if stage["canonical_stage_type"] == "ACTIVE_FERMENTATION"
    )
    fixture = {
        "active_stage_id": active["id"],
        "fermentation_revision": body["revision"],
    }
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_temp_payload(fixture, value="25.0"),
    )
    assert response.status_code == 201, response.text
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    current = [d for d in detail["deviations"] if d["status"] == "CURRENT"]
    assert len(current) == 1
    assert Decimal(current[0]["target_value"]) == Decimal("19.0")
