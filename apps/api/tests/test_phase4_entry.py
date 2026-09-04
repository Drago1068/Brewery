import uuid

import pytest
from sqlalchemy import select

from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage
from brewing_api.domain.fermentation.models import (
    FermentationOgConsumption,
    FermentationYeastPitchReference,
)
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
    return payload


@pytest.fixture
def completed_brew_with_pitch(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    command = active_mash["command"]

    for kind, value, unit in [
        ("MASH_PH", "5.30", "pH"),
        ("MASH_GRAVITY", "1.048", "SG"),
    ]:
        response = client.post(
            f"/api/v1/brew-sessions/stages/{stage_id}/measurements",
            json=_measurement(
                kind,
                value,
                unit,
                method="METER" if kind == "MASH_PH" else "HYDROMETER",
                sample_temperature_c="65.00" if kind == "MASH_PH" else "20.00",
                temperature_compensated=True if kind == "MASH_PH" else None,
            ),
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

    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    assert details["status"] == "COMPLETED"
    return {
        "client": client,
        "session_id": session_id,
        "og_measurement_id": og.json()["id"],
        "pitch_handoff_id": pitch.json()["id"],
        "command": command,
    }


def test_start_fermentation_session_from_completed_brew(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    operation_id = str(uuid.uuid4())

    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": operation_id},
    )
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["status"] == "ACTIVE"
    assert body["brew_session_id"] == brew_session_id
    assert body["og_consumption"]["brew_measurement_id"] == completed_brew_with_pitch[
        "og_measurement_id"
    ]
    assert body["og_consumption"]["og_availability"] == "KNOWN"
    assert body["og_consumption"]["is_current"] is True
    assert body["yeast_pitch_reference"]["brew_pitch_handoff_id"] == completed_brew_with_pitch[
        "pitch_handoff_id"
    ]
    stage_types = {stage["canonical_stage_type"]: stage["status"] for stage in body["stages"]}
    assert stage_types["PITCH_CONFIRMED"] == "COMPLETED"
    assert stage_types["ACTIVE_FERMENTATION"] == "ACTIVE"

    replay = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": operation_id},
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == body["id"]

    with SessionLocal() as db:
        og = db.scalar(select(FermentationOgConsumption))
        assert og is not None
        assert str(og.brew_measurement_id) == completed_brew_with_pitch["og_measurement_id"]
        yeast = db.scalar(select(FermentationYeastPitchReference))
        assert yeast is not None
        assert yeast.yeast_note.startswith("US-05")


def test_start_fermentation_rejects_incomplete_brew(active_mash):
    client = active_mash["client"]
    response = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{active_mash['session_id']}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "BREW_SESSION_NOT_COMPLETED"


def test_start_fermentation_requires_pitch_handoff(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    command = active_mash["command"]

    for kind, value, unit in [("MASH_PH", "5.30", "pH"), ("MASH_GRAVITY", "1.048", "SG")]:
        assert (
            client.post(
                f"/api/v1/brew-sessions/stages/{stage_id}/measurements",
                json=_measurement(
                    kind,
                    value,
                    unit,
                    method="METER" if kind == "MASH_PH" else "HYDROMETER",
                    sample_temperature_c="65.00" if kind == "MASH_PH" else "20.00",
                    temperature_compensated=True if kind == "MASH_PH" else None,
                ),
            ).status_code
            == 201
        )

    post_boil_id = uuid.uuid4()
    with SessionLocal() as db:
        session = db.get(BrewSession, uuid.UUID(session_id))
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

    assert (
        client.post(
            f"/api/v1/brew-sessions/stages/{post_boil_id}/measurements",
            json=_measurement("ORIGINAL_GRAVITY", "1.052", "SG"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v1/brew-sessions/stages/{stage_id}/complete",
            json=command(),
        ).status_code
        == 200
    )

    response = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "PITCH_HANDOFF_REQUIRED"
