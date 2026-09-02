"""Phase 4 Slice 2 §12 measurement-type matrix (P4-FR-025..028, P4-AC-020)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from phase4_fixtures import started_fermentation  # noqa: F401


def _payload(
    started: dict,
    *,
    measurement_type: str,
    value: str,
    unit: str,
    method: str,
    stage_instance_id: str | None = None,
) -> dict:
    return {
        "operation_id": str(uuid.uuid4()),
        "measurement_type": measurement_type,
        "value": value,
        "unit": unit,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "stage_instance_id": stage_instance_id or started["active_stage_id"],
        "method": method,
        "source": "OBSERVED",
    }


@pytest.mark.parametrize(
    ("value", "unit", "expected_status"),
    [
        ("-5", "degC", 201),
        ("40", "degC", 201),
        ("20", "degC", 201),
        ("23", "degF", 201),
        ("-5.1", "degC", 422),
        ("40.1", "degC", 422),
        ("140", "degF", 422),
    ],
)
def test_fermentation_temperature_bounds(started_fermentation, value, unit, expected_status):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_payload(
            started_fermentation,
            measurement_type="FERMENTATION_TEMPERATURE",
            value=value,
            unit=unit,
            method="THERMOMETER",
        ),
    )
    assert response.status_code == expected_status, response.text
    if expected_status == 201:
        assert response.json()["canonical_unit"] == "degC"


@pytest.mark.parametrize(
    ("value", "expected_status"),
    [
        ("2.5", 201),
        ("8.0", 201),
        ("5.2", 201),
        ("2.49", 422),
        ("8.01", 422),
    ],
)
def test_fermentation_ph_bounds(started_fermentation, value, expected_status):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_payload(
            started_fermentation,
            measurement_type="FERMENTATION_PH",
            value=value,
            unit="pH",
            method="METER",
        ),
    )
    assert response.status_code == expected_status, response.text


@pytest.mark.parametrize(
    ("value", "unit", "expected_status"),
    [
        ("0.900", "SG", 201),
        ("1.300", "SG", 201),
        ("0.899", "SG", 422),
        ("1.301", "SG", 422),
    ],
)
def test_fermentation_gravity_bounds(started_fermentation, value, unit, expected_status):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    body = _payload(
        started_fermentation,
        measurement_type="FERMENTATION_GRAVITY",
        value=value,
        unit=unit,
        method="HYDROMETER",
    )
    body["sample_temperature_c"] = "20.00"
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=body,
    )
    assert response.status_code == expected_status, response.text


def test_conditioning_temperature_bounds_on_conditioning_stage(started_fermentation):
    import uuid as _uuid

    from brewing_api.domain.fermentation.models import FermentationStageInstance
    from brewing_api.platform.database import SessionLocal
    from brewing_api.platform.time import utc_now

    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    conditioning_stage = next(
        stage
        for stage in started_fermentation["fermentation"]["stages"]
        if stage["canonical_stage_type"] == "CONDITIONING"
    )["id"]
    now = utc_now()
    with SessionLocal() as db:
        stage = db.get(FermentationStageInstance, _uuid.UUID(conditioning_stage))
        assert stage is not None
        stage.status = "ACTIVE"
        stage.started_at = now
        stage.first_started_at = now
        stage.current_activation_started_at = now
        db.commit()

    for value, expected in [("-5", 201), ("30", 201), ("18", 201), ("30.1", 422)]:
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/measurements",
            json=_payload(
                started_fermentation,
                measurement_type="CONDITIONING_TEMPERATURE",
                value=value,
                unit="degC",
                method="PROBE",
                stage_instance_id=conditioning_stage,
            ),
        )
        assert response.status_code == expected, response.text

    wrong_stage = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_payload(
            started_fermentation,
            measurement_type="CONDITIONING_TEMPERATURE",
            value="18",
            unit="degC",
            method="PROBE",
        ),
    )
    assert wrong_stage.status_code == 422
    assert wrong_stage.json()["code"] == "STAGE_TYPE_MISMATCH"


@pytest.mark.parametrize(
    ("measurement_type", "method", "missing_method_status"),
    [
        ("FERMENTATION_TEMPERATURE", "THERMOMETER", 201),
        ("FERMENTATION_PH", "METER", 201),
        ("FERMENTATION_GRAVITY", "HYDROMETER", 201),
    ],
)
def test_measurement_method_required(
    started_fermentation, measurement_type, method, missing_method_status
):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    body = _payload(
        started_fermentation,
        measurement_type=measurement_type,
        value="20" if measurement_type.endswith("TEMPERATURE") else "5.2",
        unit="degC" if measurement_type.endswith("TEMPERATURE") else "pH",
        method=method,
    )
    if measurement_type == "FERMENTATION_GRAVITY":
        body["value"] = "1.040"
        body["unit"] = "SG"
        body["sample_temperature_c"] = "20.00"
    accepted = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=body,
    )
    assert accepted.status_code == missing_method_status, accepted.text

    body.pop("method")
    rejected = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={**body, "operation_id": str(uuid.uuid4())},
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "MEASUREMENT_CONTEXT_REQUIRED"
