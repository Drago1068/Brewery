"""Slice 2 closure: PostgreSQL interleaving, late entry, recovery."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from brewing_api.application.errors import ConflictError
from brewing_api.application.phase4.measurements import (
    CorrectionCommand,
    MeasurementCommand,
    correct_measurement,
    record_measurement,
)
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationMeasurement,
    FermentationMeasurementCorrection,
    FermentationSession,
    FermentationStageInstance,
    FermentationYeastPitchReference,
)
from brewing_api.domain.identity.models import User
from brewing_api.main import app
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now

from phase4_fixtures import started_fermentation  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("TEST_USE_POSTGRES") != "1",
        reason="Slice 2 closure interleaving requires PostgreSQL (TEST_USE_POSTGRES=1)",
    ),
]

_LATE_REASON = "Recorded after hydrometer reading was found in notebook from yesterday"
_CORRECTION_REASON = "Corrected hydrometer reading after reviewing lab notes from yesterday"


def _create_gravity(client, started: dict) -> dict:
    observed_at = datetime.now(timezone.utc).isoformat()
    response = client.post(
        f"/api/v1/fermentation-sessions/{started['fermentation_session_id']}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.040",
            "unit": "SG",
            "observed_at": observed_at,
            "stage_instance_id": started["active_stage_id"],
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "source": "OBSERVED",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _race_corrections(
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    measurement_id: uuid.UUID,
    leaf_id: uuid.UUID,
    operation_ids: tuple[str, str],
) -> list[tuple[str, object]]:
    barrier = threading.Barrier(2, timeout=10)

    def worker(operation_id: str) -> tuple[str, object]:
        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                assert user is not None
                barrier.wait()
                correction = correct_measurement(
                    db,
                    user,
                    session_id,
                    measurement_id,
                    CorrectionCommand(
                        correction_of_id=leaf_id,
                        reason=_CORRECTION_REASON,
                        operation_id=operation_id,
                        value=Decimal("1.038"),
                        unit="SG",
                        method="HYDROMETER",
                    ),
                )
                return ("ok", correction)
        except ConflictError as exc:
            return ("conflict", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, operation_id) for operation_id in operation_ids]
        return [future.result(timeout=30) for future in futures]


def test_postgres_measurement_persistence_and_fk_integrity(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    created = _create_gravity(client, started_fermentation)
    corrected = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{created['id']}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": created["id"],
            "reason": _CORRECTION_REASON,
            "value": "1.038",
            "unit": "SG",
            "method": "HYDROMETER",
        },
    )
    assert corrected.status_code == 201, corrected.text

    with SessionLocal() as db:
        measurements = list(
            db.scalars(
                select(FermentationMeasurement).where(
                    FermentationMeasurement.fermentation_session_id == uuid.UUID(session_id)
                )
            ).all()
        )
        corrections = list(
            db.scalars(
                select(FermentationMeasurementCorrection).where(
                    FermentationMeasurementCorrection.fermentation_session_id
                    == uuid.UUID(session_id)
                )
            ).all()
        )
        assert len(measurements) == 1
        assert len(corrections) == 1
        assert corrections[0].correction_of_id == measurements[0].id
        assert measurements[0].stage_instance_id is not None


def test_concurrent_corrections_one_winner(started_fermentation):
    client = started_fermentation["client"]
    session_id = uuid.UUID(started_fermentation["fermentation_session_id"])
    created = _create_gravity(client, started_fermentation)
    measurement_id = uuid.UUID(created["id"])
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "brewer"))
        assert user is not None
        user_id = user.id

    results = _race_corrections(
        user_id=user_id,
        session_id=session_id,
        measurement_id=measurement_id,
        leaf_id=measurement_id,
        operation_ids=("corr-race-a", "corr-race-b"),
    )
    outcomes = [item[0] for item in results]
    assert outcomes.count("ok") == 1, results
    assert outcomes.count("conflict") == 1, results

    with SessionLocal() as db:
        corrections = list(
            db.scalars(
                select(FermentationMeasurementCorrection).where(
                    FermentationMeasurementCorrection.fermentation_session_id == session_id
                )
            ).all()
        )
        assert len(corrections) == 1
        events = list(
            db.scalars(
                select(FermentationJournalEvent).where(
                    FermentationJournalEvent.fermentation_session_id == session_id,
                    FermentationJournalEvent.event_type == "FERMENTATION_MEASUREMENT_CORRECTED",
                )
            ).all()
        )
        assert len(events) == 1


def test_late_entry_on_completed_stage(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    ferm_id = uuid.UUID(session_id)
    with SessionLocal() as db:
        pitch = db.scalar(
            select(FermentationYeastPitchReference).where(
                FermentationYeastPitchReference.fermentation_session_id == ferm_id
            )
        )
        stage = db.get(FermentationStageInstance, uuid.UUID(started_fermentation["active_stage_id"]))
        assert pitch is not None and stage is not None
        now = utc_now()
        pitched_at = now - timedelta(hours=3)
        pitch.pitched_at = pitched_at
        stage.status = "COMPLETED"
        stage.first_started_at = pitched_at + timedelta(minutes=10)
        stage.completed_at = pitched_at + timedelta(hours=2)
        stage.first_completed_at = stage.completed_at
        db.commit()
        observed_at = pitched_at + timedelta(hours=1)

    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.036",
            "unit": "SG",
            "observed_at": observed_at.isoformat(),
            "stage_instance_id": started_fermentation["active_stage_id"],
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "source": "OBSERVED",
            "late_entry_reason": _LATE_REASON,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["late_entry"] is True


def test_late_entry_window_closed_rejects(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    now = utc_now()
    with SessionLocal() as db:
        stage = db.get(FermentationStageInstance, uuid.UUID(started_fermentation["active_stage_id"]))
        assert stage is not None
        stage.status = "COMPLETED"
        stage.first_started_at = now - timedelta(hours=30)
        stage.completed_at = now - timedelta(hours=25)
        stage.first_completed_at = stage.completed_at
        db.commit()

    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.036",
            "unit": "SG",
            "observed_at": (now - timedelta(hours=26)).isoformat(),
            "stage_instance_id": started_fermentation["active_stage_id"],
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "source": "OBSERVED",
            "late_entry_reason": _LATE_REASON,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "LATE_ENTRY_WINDOW_CLOSED"


def test_recovery_reload_after_new_test_client(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    operation_id = "recovery-meas-1"
    observed_at = datetime.now(timezone.utc).isoformat()
    created = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": operation_id,
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.040",
            "unit": "SG",
            "observed_at": observed_at,
            "stage_instance_id": started_fermentation["active_stage_id"],
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "source": "OBSERVED",
        },
    )
    assert created.status_code == 201, created.text
    measurement_id = created.json()["id"]

    with TestClient(app) as fresh_client:
        fresh_client.headers["Origin"] = "http://testserver"
        login = fresh_client.post(
            "/api/v1/auth/login",
            json={"username": "brewer", "password": "test-password-not-a-secret"},
        )
        assert login.status_code == 200
        fresh_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        replay = fresh_client.post(
            f"/api/v1/fermentation-sessions/{session_id}/measurements",
            json={
                "operation_id": operation_id,
                "measurement_type": "FERMENTATION_GRAVITY",
                "value": "1.040",
                "unit": "SG",
                "observed_at": observed_at,
                "stage_instance_id": started_fermentation["active_stage_id"],
                "method": "HYDROMETER",
                "sample_temperature_c": "20.00",
                "source": "OBSERVED",
            },
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == measurement_id
        details = fresh_client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
        assert len(details["measurements"]) == 1
        assert details["derived_gravity"]["stable_gravity_status"] == "INSUFFICIENT_EVIDENCE"


def test_stale_revision_rejects_second_measurement(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    details = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    revision = details["revision"]
    observed_at = datetime.now(timezone.utc).isoformat()
    first = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.040",
            "unit": "SG",
            "observed_at": observed_at,
            "stage_instance_id": started_fermentation["active_stage_id"],
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "source": "OBSERVED",
            "expected_revision": revision,
        },
    )
    assert first.status_code == 201, first.text
    stale = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.038",
            "unit": "SG",
            "observed_at": observed_at,
            "stage_instance_id": started_fermentation["active_stage_id"],
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "source": "OBSERVED",
            "expected_revision": revision,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_REVISION"
