"""CODEX-001 / P4-FR-077 / P4-AC-067 — closed command schema unknown-field rejection."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationOperation,
)
from brewing_api.platform.database import SessionLocal
from brewing_api.presentation.phase4_schemas import (
    Phase4ClosedCommand,
    phase4_closed_command_models,
)
from brewing_api.presentation.routes import fermentation_sessions as routes

# Concrete closed JSON command schemas (multipart media upload excluded — Form, not JSON body).
EXPECTED_CLOSED_SCHEMA_NAMES = frozenset(
    {
        "AbortCommand",
        "AssessPackagingReadinessRequest",
        "CancelTimerCommand",
        "CompleteConditioningRequest",
        "CompleteFermentationRequest",
        "CorrectAdditionRequest",
        "CorrectMeasurementCommand",
        "CreateNoteCommand",
        "EnrichYeastReferenceCommand",
        "ExecutePlannedAdditionRequest",
        "ExtendTimerCommand",
        "OperationOnlyCommand",
        "RecordActionRequest",
        "RecordMeasurementCommand",
        "RecordPackagingHandoffRequest",
        "RecordUnplannedAdditionRequest",
        "RecordWaiverRequest",
        "ReconcileOgCommandBody",
        "RemoveAttachmentCommand",
        "RevisionCommand",
        "StartAuxiliaryTimerCommand",
        "StartFermentationCommand",
    }
)


def test_structural_guard_all_closed_schemas_forbid_extras():
    models = phase4_closed_command_models()
    names = {cls.__name__ for cls in models}
    assert names == EXPECTED_CLOSED_SCHEMA_NAMES
    for cls in models:
        assert issubclass(cls, Phase4ClosedCommand)
        assert cls.model_config.get("extra") == "forbid"
        with pytest.raises(ValidationError) as exc_info:
            cls.model_validate({"__unknown_structural__": True})
        assert any(err["type"] == "extra_forbidden" for err in exc_info.value.errors())


def test_ac067_unknown_field_on_start_conditioning(started_fermentation):
    """P4-AC-067 exact: 422 UNKNOWN_FIELD, no domain/journal/operation-success rows."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert detail.status_code == 200
    revision = detail.json()["revision"]

    with SessionLocal() as db:
        ops_before = db.scalar(select(func.count()).select_from(FermentationOperation)) or 0
        journal_before = db.scalar(select(func.count()).select_from(FermentationJournalEvent)) or 0

    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": revision,
            "status": "CLOSED",
            "owner_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "UNKNOWN_FIELD"
    assert "detail" in body

    after = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert after.status_code == 200
    assert after.json()["revision"] == revision
    assert after.json()["status"] == detail.json()["status"]

    with SessionLocal() as db:
        ops_after = db.scalar(select(func.count()).select_from(FermentationOperation)) or 0
        journal_after = db.scalar(select(func.count()).select_from(FermentationJournalEvent)) or 0
    assert ops_after == ops_before
    assert journal_after == journal_before


def test_ac067_unknown_field_on_measurement_mixed_with_valid(
    started_fermentation,
):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    revision = detail.json()["revision"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_TEMPERATURE",
            "value": "18.5",
            "unit": "C",
            "observed_at": datetime.now(UTC).isoformat(),
            "stage_instance_id": stage_id,
            "expected_revision": revision,
            "status": "ACTIVE",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "UNKNOWN_FIELD"
    after = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert after.json()["revision"] == revision


def test_missing_required_field_is_not_unknown_field(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    revision = detail.json()["revision"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={"expected_revision": revision},
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body.get("code") != "UNKNOWN_FIELD"
    assert isinstance(body.get("detail"), list)


def test_invalid_type_is_not_unknown_field(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": "not-an-int",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json().get("code") != "UNKNOWN_FIELD"


def test_invalid_enum_action_is_not_unknown_field(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    revision = detail.json()["revision"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/actions",
        json={
            "operation_id": str(uuid.uuid4()),
            "action_type": "NOT_A_REAL_ACTION",
            "occurred_at": datetime.now(UTC).isoformat(),
            "expected_revision": revision,
        },
    )
    # Domain rejects invalid enum after schema accept — must not be UNKNOWN_FIELD
    assert response.status_code in {409, 422}, response.text
    if response.status_code == 422 and isinstance(response.json().get("detail"), str):
        assert response.json().get("code") != "UNKNOWN_FIELD"
    elif response.status_code == 422:
        assert response.json().get("code") != "UNKNOWN_FIELD"
    else:
        assert response.json().get("code") != "UNKNOWN_FIELD"


def test_valid_pause_still_succeeds(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    revision = detail.json()["revision"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": revision,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PAUSED"


def test_unknown_field_idempotency_key_not_recorded(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    revision = detail.json()["revision"]
    op_id = str(uuid.uuid4())
    bad = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={
            "operation_id": op_id,
            "expected_revision": revision,
            "forged_revision": 999,
        },
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "UNKNOWN_FIELD"
    # Same key without unknown field must succeed as a fresh command (no prior success)
    good = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={
            "operation_id": op_id,
            "expected_revision": revision,
        },
    )
    assert good.status_code == 200, good.text


def test_route_module_exports_expected_closed_count():
    assert len(EXPECTED_CLOSED_SCHEMA_NAMES) == 22
    assert len(phase4_closed_command_models()) == 22
    # Sanity: RevisionCommand still forbids extras after inheritance
    assert routes.RevisionCommand.model_config.get("extra") == "forbid"
