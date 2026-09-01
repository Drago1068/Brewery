"""Shared Phase 4 test fixtures."""

import uuid

import pytest
from sqlalchemy import select

from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage
from brewing_api.domain.measurements.models import Measurement
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now


def _measurement(kind: str, value: str, unit: str, **extra) -> dict:
    payload = {
        "measurement_type": kind,
        "value": value,
        "unit": unit,
        "operation_id": str(uuid.uuid4()),
        **extra,
    }
    if kind == "ORIGINAL_GRAVITY":
        payload.setdefault("method", "HYDROMETER")
        payload.setdefault("sample_temperature_c", "20.00")
    elif kind == "MASH_PH":
        payload.setdefault("method", "METER")
        payload.setdefault("sample_temperature_c", "65.00")
        payload.setdefault("temperature_compensated", True)
    elif kind in {"MASH_GRAVITY", "POST_MASH_GRAVITY", "PRE_BOIL_GRAVITY"}:
        payload.setdefault("method", "HYDROMETER")
        payload.setdefault("sample_temperature_c", "20.00")
    return payload


@pytest.fixture
def completed_brew_with_pitch(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    command = active_mash["command"]

    for kind, value, unit in [("MASH_PH", "5.30", "pH"), ("MASH_GRAVITY", "1.048", "SG")]:
        response = client.post(
            f"/api/v1/brew-sessions/stages/{stage_id}/measurements",
            json=_measurement(kind, value, unit),
        )
        assert response.status_code == 201, response.text

    post_boil_id = uuid.uuid4()
    with SessionLocal() as db:
        session = db.get(BrewSession, uuid.UUID(session_id))
        assert session is not None
        now = utc_now()
        db.add(
            BrewStage(
                id=post_boil_id,
                brew_session_id=session.id,
                name="POST_BOIL",
                canonical_stage_type="POST_BOIL",
                status="ACTIVE",
                started_at=now,
                target_duration_seconds=3600,
                target_temperature=session.target_mash_temperature,
                temperature_unit=session.mash_temperature_unit,
                target_ph=session.target_mash_ph,
                ph_tolerance=session.mash_ph_tolerance,
                target_gravity=session.target_mash_gravity,
                gravity_tolerance=session.mash_gravity_tolerance,
            )
        )
        db.commit()

    og = client.post(
        f"/api/v1/brew-sessions/stages/{post_boil_id}/measurements",
        json=_measurement("ORIGINAL_GRAVITY", "1.052", "SG"),
    )
    assert og.status_code == 201, og.text

    pitch = client.post(
        f"/api/v1/brew-sessions/{session_id}/pitch-handoff",
        json=command(
            yeast_addition_note="US-05 dry yeast pitched",
            pitch_temperature_c="18.0",
        ),
    )
    assert pitch.status_code == 201, pitch.text

    completed = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/complete",
        json=command(),
    )
    assert completed.status_code == 200, completed.text
    return {
        "client": client,
        "session_id": session_id,
        "og_measurement_id": og.json()["id"],
        "pitch_handoff_id": pitch.json()["id"],
        "command": command,
    }


@pytest.fixture
def started_fermentation(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201, started.text
    body = started.json()
    active_stage = next(
        stage for stage in body["stages"] if stage["canonical_stage_type"] == "ACTIVE_FERMENTATION"
    )
    return {
        **completed_brew_with_pitch,
        "fermentation_session_id": body["id"],
        "fermentation_revision": body["revision"],
        "active_stage_id": active_stage["id"],
        "fermentation": body,
    }
