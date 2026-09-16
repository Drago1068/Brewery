# ruff: noqa: F811 - test parameters intentionally shadow the fixture import

import uuid
from datetime import UTC, datetime

from phase4_fixtures import completed_brew_with_pitch, started_fermentation  # noqa: F401
from sqlalchemy import select

from brewing_api.domain.fermentation.models import (
    FermentationMeasurement,
    FermentationMeasurementCorrection,
)
from brewing_api.platform.database import SessionLocal


def _gravity_payload(
    started: dict,
    *,
    value: str = "1.040",
    operation_id: str | None = None,
    observed_at: datetime | None = None,
) -> dict:
    when = observed_at or datetime.now(UTC)
    return {
        "operation_id": operation_id or str(uuid.uuid4()),
        "measurement_type": "FERMENTATION_GRAVITY",
        "value": value,
        "unit": "SG",
        "observed_at": when.isoformat(),
        "stage_instance_id": started["active_stage_id"],
        "method": "HYDROMETER",
        "sample_temperature_c": "20.00",
        "source": "OBSERVED",
    }


def test_record_fermentation_gravity_and_derived_state(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(started_fermentation),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["measurement_type"] == "FERMENTATION_GRAVITY"
    assert body["canonical_unit"] == "SG"
    assert body["late_entry"] is False

    details = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert len(details["measurements"]) == 1
    assert details["derived_gravity"]["stable_gravity_status"] == "INSUFFICIENT_EVIDENCE"


def test_measurement_idempotency_replay_and_conflict(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    operation_id = "meas-op-1"
    observed_at = datetime.now(UTC)
    first = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(
            started_fermentation,
            operation_id=operation_id,
            observed_at=observed_at,
        ),
    )
    assert first.status_code == 201
    replay = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(
            started_fermentation,
            operation_id=operation_id,
            observed_at=observed_at,
        ),
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]

    conflict = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(
            started_fermentation,
            operation_id=operation_id,
            value="1.030",
            observed_at=observed_at,
        ),
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_measurement_correction_chain_updates_derived_leaf(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    created = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(started_fermentation, value="1.040"),
    ).json()
    correction = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{created['id']}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": created["id"],
            "reason": "Hydrometer meniscus read at the wrong line on the scale",
            "value": "1.038",
            "unit": "SG",
            "method": "HYDROMETER",
        },
    )
    assert correction.status_code == 201, correction.text
    assert correction.json()["canonical_value"] == "1.038000"
    assert correction.json()["current_correction_id"] == correction.json()["correction_id"]

    with SessionLocal() as db:
        original = db.get(FermentationMeasurement, uuid.UUID(created["id"]))
        assert original is not None
        assert str(original.canonical_value) == "1.040000"
        corrections = list(db.scalars(select(FermentationMeasurementCorrection)).all())
        assert len(corrections) == 1


def test_plato_measurement_rejects_out_of_domain(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            **_gravity_payload(started_fermentation),
            "value": "100",
            "unit": "Plato",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "PLATO_OUT_OF_DOMAIN"


def test_rejects_measurement_on_wrong_stage_type(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    pitch_stage = next(
        stage
        for stage in started_fermentation["fermentation"]["stages"]
        if stage["canonical_stage_type"] == "PITCH_CONFIRMED"
    )["id"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            **_gravity_payload(started_fermentation),
            "stage_instance_id": pitch_stage,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "STAGE_TYPE_MISMATCH"
