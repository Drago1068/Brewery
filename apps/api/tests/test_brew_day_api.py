import uuid
from datetime import timedelta

from sqlalchemy import select

from brewing_api.domain.audit.models import BrewJournalEvent
from brewing_api.domain.brew_sessions.models import BrewSession, BrewTimer
from brewing_api.domain.measurements.models import Measurement
from brewing_api.platform.database import SessionLocal


def test_session_and_mash_state_transitions(active_mash: dict):
    client = active_mash["client"]
    response = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["mash"]["status"] == "ACTIVE"
    assert body["mash"]["timer"]["status"] == "RUNNING"
    assert body["mash"]["notifications"][0]["message"] == "Measure Mash pH"


def test_timer_recovery_uses_persisted_server_timestamp(active_mash: dict):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    with SessionLocal() as db:
        timer = db.scalar(select(BrewTimer))
        assert timer is not None
        original_start = timer.started_at
        timer.started_at = timer.started_at - timedelta(seconds=125)
        db.commit()

    first = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    second = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    assert first["mash"]["timer"]["started_at"] == second["mash"]["timer"]["started_at"]
    assert first["mash"]["timer"]["elapsed_seconds"] >= 125
    assert first["mash"]["timer"]["started_at"] != original_start.isoformat()


def test_measurement_validation_and_deviation_rules(active_mash: dict):
    client = active_mash["client"]
    stage_id = active_mash["stage_id"]

    invalid_ph = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/measurements",
        json={"measurement_type": "MASH_PH", "value": "14.5", "unit": "pH"},
    )
    assert invalid_ph.status_code == 422

    ph = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/measurements",
        json={
            "measurement_type": "MASH_PH",
            "value": "5.34",
            "unit": "pH",
            "instrument": "Calibrated meter",
        },
    )
    assert ph.status_code == 201
    assert ph.json()["deviation_created"] is False

    gravity = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/measurements",
        json={"measurement_type": "MASH_GRAVITY", "value": "1.044", "unit": "SG"},
    )
    assert gravity.status_code == 201
    assert gravity.json()["deviation_created"] is True


def test_mash_completion_requires_measurements(active_mash: dict):
    response = active_mash["client"].post(
        f"/api/v1/brew-sessions/stages/{active_mash['stage_id']}/complete"
    )
    assert response.status_code == 400
    assert "MASH_PH" in response.json()["detail"]


def test_complete_slice_generates_journal_and_preserves_history(active_mash: dict):
    client = active_mash["client"]
    stage_id = active_mash["stage_id"]
    session_id = active_mash["session_id"]
    recorded = []
    for kind, value, unit in [
        ("MASH_PH", "5.42", "pH"),
        ("MASH_GRAVITY", "1.048", "SG"),
    ]:
        response = client.post(
            f"/api/v1/brew-sessions/stages/{stage_id}/measurements",
            json={"measurement_type": kind, "value": value, "unit": unit},
        )
        assert response.status_code == 201
        recorded.append(response.json())

    completed = client.post(f"/api/v1/brew-sessions/stages/{stage_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"

    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    assert details["status"] == "COMPLETED"
    assert details["planned"]["mash_ph"] == "5.30"
    assert any(item["value"] == "5.420" for item in details["mash"]["measurements"])
    event_types = {item["event_type"] for item in details["journal"]}
    assert {
        "BREW_SESSION_STARTED",
        "BREW_STAGE_STARTED",
        "BREW_TIMER_STARTED",
        "BREW_MEASUREMENT_DUE",
        "BREW_MEASUREMENT_RECORDED",
        "BREW_VARIANCE_DETECTED",
        "BREW_STAGE_COMPLETED",
    } <= event_types

    correction = client.post(
        f"/api/v1/brew-sessions/measurements/{recorded[0]['id']}/corrections",
        json={
            "measurement_type": "MASH_PH",
            "value": "5.40",
            "unit": "pH",
            "note": "Transcription correction",
        },
    )
    assert correction.status_code == 201
    assert correction.json()["correction_of_id"] == recorded[0]["id"]
    with SessionLocal() as db:
        original = db.get(Measurement, uuid.UUID(recorded[0]["id"]))
        assert str(original.value) == "5.420"
        session = db.get(BrewSession, uuid.UUID(session_id))
        assert session.status == "COMPLETED"
        correction_event = db.scalar(
            select(BrewJournalEvent).where(
                BrewJournalEvent.event_type == "BREW_MEASUREMENT_CORRECTED"
            )
        )
        assert correction_event is not None
