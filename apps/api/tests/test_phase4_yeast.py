"""Slice 6 yeast provenance and pitch history (API + domain, SQLite)."""

from __future__ import annotations

import uuid

from phase4_fixtures import started_fermentation  # noqa: F401
from phase4_yeast_helpers import create_ingredient_lot, create_source_fermentation_session
from sqlalchemy import select

from brewing_api.application.auth import password_hash
from brewing_api.domain.fermentation.models import (
    FermentationYeastPitchReference,
    FermentationYeastReferenceHistory,
)
from brewing_api.domain.identity.models import User
from brewing_api.domain.ingredients.models import Ingredient
from brewing_api.platform.database import SessionLocal

_YEAST_URL = "/api/v1/fermentation-sessions/{session_id}/yeast-reference"


def _current_reference_id(client, session_id: str) -> str:
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert detail.status_code == 200, detail.text
    reference = detail.json()["yeast_pitch_reference"]
    assert reference is not None
    return reference["id"]


def test_lot_linkage_immutable_snapshot(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    lot_id, ingredient_id = create_ingredient_lot(
        manufacturer="Wyeast Labs", strain="1056 American Ale"
    )

    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={"operation_id": str(uuid.uuid4()), "ingredient_lot_id": str(lot_id)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ingredient_lot_id"] == str(lot_id)
    assert body["lot_snapshot"]["manufacturer"] == "Wyeast Labs"
    assert body["lot_snapshot"]["strain"] == "1056 American Ale"

    with SessionLocal() as db:
        live_ingredient = db.get(Ingredient, ingredient_id)
        assert live_ingredient is not None
        live_ingredient.manufacturer = "Changed Labs"
        db.commit()

    history = client.get(f"/api/v1/fermentation-sessions/pitch-history?session_id={session_id}")
    assert history.status_code == 200, history.text
    snapshot = history.json()[0]["lot_snapshot"]
    assert snapshot["manufacturer"] == "Wyeast Labs"


def test_lot_of_other_user_returns_404(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]

    with SessionLocal() as db:
        other = User(
            username="yeast-other-owner",
            password_hash=password_hash.hash("other-password-not-a-secret"),
        )
        db.add(other)
        db.commit()
        other_id = other.id

    other_lot_id, _ = create_ingredient_lot(owner_id=other_id)
    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={"operation_id": str(uuid.uuid4()), "ingredient_lot_id": str(other_lot_id)},
    )
    assert response.status_code == 404, response.text


def test_source_pair_must_be_complete_or_absent(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    source_session_id, _ = create_source_fermentation_session()

    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": str(uuid.uuid4()),
            "source_fermentation_session_id": str(source_session_id),
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "SOURCE_PAIR_INCOMPLETE"


def test_source_pair_mismatch_returns_422(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    source_session_id, _ = create_source_fermentation_session()
    _, other_ref_id = create_source_fermentation_session()

    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": str(uuid.uuid4()),
            "source_fermentation_session_id": str(source_session_id),
            "source_yeast_reference_id": str(other_ref_id),
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "SOURCE_PAIR_MISMATCH"


def test_aborted_source_returns_422(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    source_session_id, source_ref_id = create_source_fermentation_session(status="ABORTED")

    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": str(uuid.uuid4()),
            "source_fermentation_session_id": str(source_session_id),
            "source_yeast_reference_id": str(source_ref_id),
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "SOURCE_SESSION_ABORTED"


def test_unfinished_source_returns_422(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    source_session_id, source_ref_id = create_source_fermentation_session(status="ACTIVE")

    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": str(uuid.uuid4()),
            "source_fermentation_session_id": str(source_session_id),
            "source_yeast_reference_id": str(source_ref_id),
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "SOURCE_SESSION_NOT_FINISHED"


def test_source_temporal_invalid_returns_422(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    from datetime import timedelta

    source_session_id, source_ref_id = create_source_fermentation_session(
        pitched_at_offset=timedelta(hours=-3)
    )

    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": str(uuid.uuid4()),
            "source_fermentation_session_id": str(source_session_id),
            "source_yeast_reference_id": str(source_ref_id),
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "SOURCE_TEMPORAL_INVALID"


def test_self_reference_rejected_422(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    reference_id = _current_reference_id(client, session_id)

    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": str(uuid.uuid4()),
            "source_fermentation_session_id": session_id,
            "source_yeast_reference_id": reference_id,
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "YEAST_LINEAGE_CYCLE"


def test_per_session_single_reference_and_history_append_only(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]

    first = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": str(uuid.uuid4()),
            "preparation_method_note": "rehydrated 10 minutes",
            "pitch_inputs": {"viability_percent": {"value": 90, "source": "MANUFACTURER_PROVIDED"}},
        },
    )
    assert first.status_code == 200, first.text

    second = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": str(uuid.uuid4()),
            "preparation_method_note": "rehydrated 20 minutes",
            "reason": "corrected preparation note",
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["preparation_method_note"] == "rehydrated 20 minutes"

    with SessionLocal() as db:
        references = list(db.scalars(select(FermentationYeastPitchReference)).all())
        assert len(references) == 1
        history = list(
            db.scalars(
                select(FermentationYeastReferenceHistory).order_by(
                    FermentationYeastReferenceHistory.created_at
                )
            ).all()
        )
        assert len(history) == 2
        assert history[0].new_snapshot["preparation_method_note"] == "rehydrated 10 minutes"
        assert history[1].prior_snapshot["preparation_method_note"] == "rehydrated 10 minutes"


def test_idempotency_replay_and_conflict(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    operation_id = "yeast-enrich-replay-1"

    first = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": operation_id,
            "preparation_method_note": "rehydrated 10 minutes",
        },
    )
    assert first.status_code == 200, first.text

    replay = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": operation_id,
            "preparation_method_note": "rehydrated 10 minutes",
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]

    conflict = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": operation_id,
            "preparation_method_note": "rehydrated 30 minutes",
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_pitch_history_filters_by_session_and_lot(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    lot_id, _ = create_ingredient_lot()

    link = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={"operation_id": str(uuid.uuid4()), "ingredient_lot_id": str(lot_id)},
    )
    assert link.status_code == 200, link.text

    by_session = client.get(f"/api/v1/fermentation-sessions/pitch-history?session_id={session_id}")
    assert by_session.status_code == 200, by_session.text
    assert len(by_session.json()) == 1
    assert by_session.json()[0]["ingredient_lot_id"] == str(lot_id)

    by_lot = client.get(f"/api/v1/fermentation-sessions/pitch-history?lot_id={lot_id}")
    assert by_lot.status_code == 200, by_lot.text
    assert len(by_lot.json()) == 1

    all_history = client.get("/api/v1/fermentation-sessions/pitch-history")
    assert all_history.status_code == 200
    assert len(all_history.json()) >= 1