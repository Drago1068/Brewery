"""Phase 4 §36 recovery final-acceptance campaign (Candidate 2 verification).

Executable proof uses persisted state via a new TestClient (API restart simulation).
Does not mutate product code.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationSession,
)
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now

from final_acceptance._helpers import fresh_authenticated_client, record_temperature

pytestmark = pytest.mark.integration


def test_fa_recovery_api_restart_preserves_session_ids(started_fermentation):
    """P4-FR-078 / P4-ADV-010 / §36 API restart: same session IDs after new client."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    revision = started_fermentation["fermentation_revision"]

    for i in range(5):
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/measurements",
            json={
                "operation_id": str(uuid.uuid4()),
                "measurement_type": "FERMENTATION_TEMPERATURE",
                "value": f"{18 + i * 0.1:.1f}",
                "unit": "degC",
                "method": "PROBE",
                "observed_at": utc_now().isoformat(),
                "stage_instance_id": stage_id,
                "expected_revision": revision,
                "source": "OBSERVED",
            },
        )
        assert response.status_code == 201, response.text
        revision = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]

    before = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert before.status_code == 200
    body = before.json()
    timer_ids = sorted(t["id"] for t in body["timers"])
    reminder_ids = sorted(r["id"] for r in body["reminders"])

    fresh = fresh_authenticated_client()
    after = fresh.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert after.status_code == 200, after.text
    restored = after.json()
    assert restored["id"] == session_id
    assert restored["status"] == body["status"]
    assert restored["revision"] == body["revision"]
    assert sorted(t["id"] for t in restored["timers"]) == timer_ids
    assert sorted(r["id"] for r in restored["reminders"]) == reminder_ids


def test_fa_recovery_refresh_preserves_effective_leaves(started_fermentation):
    """§36 browser refresh analog: repeated GET returns same effective IDs."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    revision = started_fermentation["fermentation_revision"]
    record_temperature(client, session_id, stage_id, revision)

    first = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    second = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["revision"] == second.json()["revision"]
    assert first.json()["status"] == second.json()["status"]


def test_fa_recovery_rolled_back_unknown_field_leaves_zero_rows(started_fermentation):
    """§36 partial failure: rejected unknown field creates no domain/op success rows."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    revision = detail.json()["revision"]
    with SessionLocal() as db:
        journal_before = db.scalar(select(func.count()).select_from(FermentationJournalEvent)) or 0
    bad = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": revision,
            "status": "CLOSED",
        },
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "UNKNOWN_FIELD"
    after = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert after.json()["revision"] == revision
    with SessionLocal() as db:
        journal_after = db.scalar(select(func.count()).select_from(FermentationJournalEvent)) or 0
    assert journal_after == journal_before


def test_fa_recovery_redis_non_authority_get_unchanged(started_fermentation):
    """P4-FR-079: Redis is non-authoritative — GET authority is PostgreSQL/SQLite."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    before = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    fresh = fresh_authenticated_client()
    after = fresh.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert after["id"] == before["id"]
    assert after["revision"] == before["revision"]
    with SessionLocal() as db:
        row = db.get(FermentationSession, uuid.UUID(session_id))
        assert row is not None
        assert row.revision == before["revision"]
