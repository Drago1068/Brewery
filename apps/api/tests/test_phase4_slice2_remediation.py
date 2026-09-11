"""Slice 2 review remediation contract tests (F-001 through F-005).

Bounded to Phase 4 Slice 2 measurement behavior. Each test proves the
specification-required deterministic response and zero domain/operation/
audit/idempotency mutation on rejection.
"""

# ruff: noqa: F811 - test parameters intentionally shadow the fixture import
# (established repository pattern for pytest fixtures).

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from calculations import fermentation as fermentation_calcs
from calculations.brewing import specific_gravity_to_plato
from phase4_fixtures import started_fermentation  # noqa: F401
from sqlalchemy import func, select

from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationMeasurement,
    FermentationMeasurementCorrection,
    FermentationOperation,
)
from brewing_api.platform.database import SessionLocal


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "measurements": db.scalar(
                select(func.count()).select_from(FermentationMeasurement)
            )
            or 0,
            "corrections": db.scalar(
                select(func.count()).select_from(FermentationMeasurementCorrection)
            )
            or 0,
            "operations": db.scalar(
                select(func.count()).select_from(FermentationOperation)
            )
            or 0,
            "journal": db.scalar(
                select(func.count()).select_from(FermentationJournalEvent)
            )
            or 0,
        }


def _revision(client, session_id: str) -> tuple[int, str]:
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert detail.status_code == 200, detail.text
    return detail.json()["revision"], detail.json()["status"]


def _record_gravity(client, session_id: str, stage_id: str) -> dict:
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.040",
            "unit": "SG",
            "observed_at": datetime.now(UTC).isoformat(),
            "stage_instance_id": stage_id,
            "method": "HYDROMETER",
            "source": "OBSERVED",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_f001_unknown_field_on_correction_rejected_without_mutation(
    started_fermentation,
):
    """F-001: unknown fields on the corrections endpoint are 422 UNKNOWN_FIELD."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    created = _record_gravity(client, session_id, stage_id)
    revision, _ = _revision(client, session_id)
    before = _counts()

    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{created['id']}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": created["id"],
            "reason": "Corrected hydrometer reading after reviewing lab notes",
            "value": "1.038",
            "unit": "SG",
            "expected_revision": revision,
            "forged_field": "not-authorized",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "UNKNOWN_FIELD"
    assert _counts() == before
    assert _revision(client, session_id)[0] == revision


def test_f002_malformed_numeric_values_rejected_without_mutation(
    started_fermentation,
):
    """F-002: malformed and non-finite numerics are 422, never HTTP 500."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    revision, _ = _revision(client, session_id)
    before = _counts()

    for bad_value in ["not-a-number", "", "1.2.3", "NaN", "Infinity", "-Infinity", "sNaN"]:
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/measurements",
            json={
                "operation_id": str(uuid.uuid4()),
                "measurement_type": "FERMENTATION_GRAVITY",
                "value": bad_value,
                "unit": "SG",
                "observed_at": datetime.now(UTC).isoformat(),
                "stage_instance_id": stage_id,
                "method": "HYDROMETER",
                "source": "OBSERVED",
            },
        )
        assert response.status_code == 422, (bad_value, response.text)
        assert response.json()["code"] == "INVALID_NUMERIC_VALUE", bad_value

    bad_temp = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_TEMPERATURE",
            "value": "18.5",
            "unit": "degC",
            "observed_at": datetime.now(UTC).isoformat(),
            "stage_instance_id": stage_id,
            "method": "PROBE",
            "source": "OBSERVED",
            "sample_temperature_c": "NaN",
        },
    )
    assert bad_temp.status_code == 422, bad_temp.text
    assert bad_temp.json()["code"] == "INVALID_NUMERIC_VALUE"

    assert _counts() == before
    assert _revision(client, session_id)[0] == revision


def test_f002_malformed_numeric_on_correction_rejected_without_mutation(
    started_fermentation,
):
    """F-002: malformed numerics on corrections are 422 with zero mutation."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    created = _record_gravity(client, session_id, stage_id)
    revision, _ = _revision(client, session_id)
    before = _counts()

    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{created['id']}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": created["id"],
            "reason": "Corrected hydrometer reading after reviewing lab notes",
            "value": "Infinity",
            "unit": "SG",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_NUMERIC_VALUE"
    assert _counts() == before
    assert _revision(client, session_id)[0] == revision


def test_f003_measurement_allowed_while_session_paused(started_fermentation):
    """F-003 positive: §18 stage windows govern; PAUSED stages accept readings."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    revision, _ = _revision(client, session_id)

    paused = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "PAUSED"

    recorded = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.038",
            "unit": "SG",
            "observed_at": datetime.now(UTC).isoformat(),
            "stage_instance_id": stage_id,
            "method": "HYDROMETER",
            "source": "OBSERVED",
        },
    )
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["late_entry"] is False

    resumed = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/resume",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id)[0],
        },
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "ACTIVE"


def test_f003_window_still_enforced_while_paused(started_fermentation):
    """F-003 negative: pause does not waive the §18 observed_at window."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    revision, _ = _revision(client, session_id)

    paused = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"operation_id": str(uuid.uuid4()), "expected_revision": revision},
    )
    assert paused.status_code == 200, paused.text
    paused_revision, _ = _revision(client, session_id)
    before = _counts()

    future = datetime.now(UTC) + timedelta(hours=2)
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.038",
            "unit": "SG",
            "observed_at": future.isoformat(),
            "stage_instance_id": stage_id,
            "method": "HYDROMETER",
            "source": "OBSERVED",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "TIMESTAMP_FUTURE"
    assert _counts() == before
    assert _revision(client, session_id)[0] == paused_revision


def test_f004_naive_correction_timestamp_rejected_without_mutation(
    started_fermentation,
):
    """F-004: corrections apply strict UTC/offset rules; naive is 422."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    created = _record_gravity(client, session_id, stage_id)
    revision, _ = _revision(client, session_id)
    before = _counts()

    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{created['id']}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": created["id"],
            "reason": "Corrected hydrometer reading after reviewing lab notes",
            "observed_at": "2026-09-01T12:00:00",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "TIMESTAMP_NOT_UTC"
    assert _counts() == before
    assert _revision(client, session_id)[0] == revision


def test_f005_plato_adapter_matches_shared_authority():
    """F-005: local Plato polynomial is provably identical to the shared authority.

    The shared ``specific_gravity_to_plato`` is undefined below SG 1.000, so
    the Slice 2 adapter (domain SG 0.900-1.300) cannot delegate unconditionally;
    this golden proves coefficient-identical behavior where both are defined.
    """
    for raw in ["1.000", "1.010", "1.040", "1.065", "1.100", "1.200", "1.300"]:
        sg = Decimal(raw)
        assert fermentation_calcs._plato_polynomial(sg) == specific_gravity_to_plato(sg)

    plato_min, plato_max = fermentation_calcs.plato_domain_bounds()
    assert plato_min < Decimal("0") < plato_max
    for sg in [Decimal("1.000"), Decimal("1.040"), Decimal("1.100"), Decimal("1.300")]:
        plato = specific_gravity_to_plato(sg)
        assert (
            abs(fermentation_calcs.plato_to_sg(plato) - sg) < Decimal("0.0000001")
        )
        round_tripped = fermentation_calcs.plato_to_sg(plato)
        assert abs(specific_gravity_to_plato(round_tripped) - plato) < Decimal("0.0000001")

    try:
        specific_gravity_to_plato(Decimal("0.999"))
    except ValueError:
        pass
    else:  # pragma: no cover - documents the authority boundary
        raise AssertionError("shared authority unexpectedly defined below SG 1.000")
