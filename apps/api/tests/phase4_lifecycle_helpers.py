"""Helpers for Phase 4 lifecycle tests."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from brewing_api.application.phase4.derived_gravity import recompute_derived_gravity
from brewing_api.application.phase4.time_validation import _coerce_aware
from brewing_api.domain.fermentation.constants import MEASUREMENT_SCHEMA_VERSION
from brewing_api.domain.fermentation.models import (
    FermentationMeasurement,
    FermentationPlanSnapshot,
    FermentationSession,
    FermentationYeastPitchReference,
)
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now


def seed_stable_gravity_measurements(
    *,
    fermentation_session_id: str,
    stage_instance_id: str,
    actor_username: str = "brewer",
    values: tuple[str, str, str] = ("1.020", "1.019", "1.018"),
) -> list[uuid.UUID]:
    """Insert three 24h-spaced gravity leaves for stable-gravity eligibility tests."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == actor_username))
        session = db.get(FermentationSession, uuid.UUID(fermentation_session_id))
        pitch = db.scalar(
            select(FermentationYeastPitchReference).where(
                FermentationYeastPitchReference.fermentation_session_id == session.id
            )
        )
        assert user is not None and session is not None and pitch is not None
        created_ids: list[uuid.UUID] = []
        base = utc_now() - timedelta(hours=50)
        now = utc_now()
        for index, value in enumerate(values):
            observed_at = base + timedelta(hours=24 * index)
            recorded_at = observed_at + timedelta(minutes=5)
            measurement = FermentationMeasurement(
                fermentation_session_id=session.id,
                stage_instance_id=uuid.UUID(stage_instance_id),
                measurement_type="FERMENTATION_GRAVITY",
                raw_value=Decimal(value),
                raw_unit="SG",
                canonical_value=Decimal(value),
                canonical_unit="SG",
                observed_at=observed_at,
                recorded_at=recorded_at,
                actor_user_id=user.id,
                source="OBSERVED",
                method="HYDROMETER",
                sample_temperature_c=Decimal("20.00"),
                validation_status="ACCEPTED",
                late_entry=_coerce_aware(observed_at) < _coerce_aware(session.started_at or now),
                operation_id=f"seed-gravity-{index}-{uuid.uuid4()}",
                schema_version=MEASUREMENT_SCHEMA_VERSION,
            )
            db.add(measurement)
            db.flush()
            created_ids.append(measurement.id)
        recompute_derived_gravity(db, session.id)
        db.commit()
    return created_ids


def record_stable_gravities(
    client: TestClient,
    *,
    session_id: str,
    stage_id: str,
    values: tuple[str, str, str] = ("1.020", "1.019", "1.018"),
) -> list[dict]:
    ids = seed_stable_gravity_measurements(
        fermentation_session_id=session_id,
        stage_instance_id=stage_id,
        values=values,
    )
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert detail.status_code == 200, detail.text
    measurements = detail.json()["measurements"]
    return [item for item in measurements if item["id"] in {str(item_id) for item_id in ids}]


def complete_fermentation(
    client: TestClient,
    *,
    session_id: str,
    revision: int,
    operation_id: str | None = None,
    override: bool = False,
    override_reason: str | None = None,
):
    payload = {
        "operation_id": operation_id or str(uuid.uuid4()),
        "expected_revision": revision,
        "override": override,
    }
    if override_reason is not None:
        payload["override_reason"] = override_reason
    return client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/complete-fermentation",
        json=payload,
    )


def set_plan_conditioning(
    *,
    session_id: str,
    conditioning_required: bool = True,
    conditioning_mode: str | None = "COLD_CONDITIONING",
    conditioning_duration_minutes: int | None = 1,
    conditioning_temperature_c: str | None = "2.0",
    temperature_tolerance_c: str = "1.0",
) -> None:
    with SessionLocal() as db:
        snapshot = db.scalar(
            select(FermentationPlanSnapshot).where(
                FermentationPlanSnapshot.fermentation_session_id == uuid.UUID(session_id)
            )
        )
        assert snapshot is not None
        payload = dict(snapshot.payload or {})
        payload["conditioning_required"] = conditioning_required
        payload["conditioning_mode"] = conditioning_mode
        payload["conditioning_duration_minutes"] = conditioning_duration_minutes
        payload["conditioning_temperature_c"] = conditioning_temperature_c
        payload["temperature_tolerance_c"] = temperature_tolerance_c
        snapshot.payload = payload
        flag_modified(snapshot, "payload")
        db.commit()


def reach_fermentation_complete(client: TestClient, started: dict) -> dict:
    session_id = started["fermentation_session_id"]
    record_stable_gravities(
        client,
        session_id=session_id,
        stage_id=started["active_stage_id"],
    )
    with SessionLocal() as db:
        revision = db.get(FermentationSession, uuid.UUID(session_id)).revision
    response = complete_fermentation(client, session_id=session_id, revision=revision)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "FERMENTATION_COMPLETE"
    return response.json()


def start_conditioning(
    client: TestClient,
    *,
    session_id: str,
    revision: int,
    operation_id: str | None = None,
):
    return client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/start-conditioning",
        json={
            "operation_id": operation_id or str(uuid.uuid4()),
            "expected_revision": revision,
        },
    )


def skip_conditioning(
    client: TestClient,
    *,
    session_id: str,
    revision: int,
    operation_id: str | None = None,
):
    return client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/skip-conditioning",
        json={
            "operation_id": operation_id or str(uuid.uuid4()),
            "expected_revision": revision,
        },
    )


def complete_conditioning(
    client: TestClient,
    *,
    session_id: str,
    revision: int,
    operation_id: str | None = None,
    override: bool = False,
    override_reason: str | None = None,
):
    payload = {
        "operation_id": operation_id or str(uuid.uuid4()),
        "expected_revision": revision,
        "override": override,
    }
    if override_reason is not None:
        payload["override_reason"] = override_reason
    return client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/complete-conditioning",
        json=payload,
    )


def backdate_conditioning_first_started(*, session_id: str, minutes_ago: int) -> None:
    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        assert session is not None
        session.conditioning_first_started_at = utc_now() - timedelta(minutes=minutes_ago)
        db.commit()
