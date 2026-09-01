import uuid
from datetime import datetime, timezone

from brewing_api.application.auth import password_hash
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal

from phase4_fixtures import started_fermentation  # noqa: F401


def test_cross_owner_measurement_access_returns_404(started_fermentation, client):
    owner_client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    observed_at = datetime.now(timezone.utc).isoformat()
    created = owner_client.post(
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
        },
    )
    assert created.status_code == 201
    measurement_id = created.json()["id"]

    with SessionLocal() as db:
        db.add(
            User(
                username="other-fermenter",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "other-fermenter", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

    assert client.get(f"/api/v1/fermentation-sessions/{session_id}").status_code == 404

    mutate = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.030",
            "unit": "SG",
            "observed_at": observed_at,
            "stage_instance_id": started_fermentation["active_stage_id"],
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "source": "OBSERVED",
        },
    )
    assert mutate.status_code == 404

    correct = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{measurement_id}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": measurement_id,
            "reason": "Attempted cross-owner correction should be rejected by ownership scope",
            "value": "1.030",
            "unit": "SG",
            "method": "HYDROMETER",
        },
    )
    assert correct.status_code == 404
