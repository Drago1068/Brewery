"""Slice 6 closure: PostgreSQL lineage integrity, cycle rejection, recovery."""
# ruff: noqa: F811 - test parameters intentionally shadow the fixture import

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from phase4_fixtures import started_fermentation  # noqa: F401
from phase4_yeast_helpers import create_ingredient_lot, create_source_fermentation_session
from sqlalchemy import select

from brewing_api.application.auth import password_hash
from brewing_api.application.errors import ConflictError
from brewing_api.application.phase4.yeast import YeastEnrichCommand, enrich_yeast_reference
from brewing_api.domain.fermentation.models import (
    FermentationYeastPitchReference,
    FermentationYeastReferenceHistory,
)
from brewing_api.domain.identity.models import User
from brewing_api.main import app
from brewing_api.platform.database import SessionLocal

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("TEST_USE_POSTGRES") != "1",
        reason="Slice 6 closure interleaving requires PostgreSQL (TEST_USE_POSTGRES=1)",
    ),
]

_YEAST_URL = "/api/v1/fermentation-sessions/{session_id}/yeast-reference"


def _seed_source_ref(source_ref_id, target_session_id, target_ref_id) -> None:
    with SessionLocal() as db:
        ref = db.get(FermentationYeastPitchReference, source_ref_id)
        assert ref is not None
        ref.source_fermentation_session_id = target_session_id
        ref.source_yeast_reference_id = target_ref_id
        db.commit()


def test_lineage_cycle_rejected_under_lock(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    current_ref_id = uuid.UUID(
        client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["yeast_pitch_reference"][
            "id"
        ]
    )

    b_session, b_ref = create_source_fermentation_session(
        pitched_at_offset=timedelta(hours=2)
    )  # pitched now - 2h
    c_session, c_ref = create_source_fermentation_session(
        pitched_at_offset=timedelta(hours=3)
    )  # pitched now - 3h

    # B reuses C (valid temporally: both backdated; C finishing).
    link_bc = client.post(
        _YEAST_URL.format(session_id=str(b_session)),
        json={
            "operation_id": str(uuid.uuid4()),
            "source_fermentation_session_id": str(c_session),
            "source_yeast_reference_id": str(c_ref),
        },
    )
    assert link_bc.status_code == 200, link_bc.text

    # Seed C -> current reference directly (bypasses temporal guard), closing a 3-cycle.
    _seed_source_ref(c_ref, uuid.UUID(session_id), current_ref_id)

    # Enrich current to reuse B: B is valid as source, but B -> C -> current forms a cycle.
    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": str(uuid.uuid4()),
            "source_fermentation_session_id": str(b_session),
            "source_yeast_reference_id": str(b_ref),
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "YEAST_LINEAGE_CYCLE"


def test_concurrent_enrichment_one_winner(started_fermentation):
    session_id = uuid.UUID(started_fermentation["fermentation_session_id"])
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "brewer"))
        assert user is not None
        user_id = user.id

    barrier = threading.Barrier(2, timeout=10)

    def worker(operation_id: str, note: str) -> tuple[str, object]:
        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                assert user is not None
                barrier.wait()
                reference = enrich_yeast_reference(
                    db,
                    user,
                    session_id,
                    YeastEnrichCommand(
                        operation_id=operation_id,
                        expected_revision=1,
                        preparation_method_note=note,
                    ),
                )
                return ("ok", reference)
        except ConflictError as exc:
            return ("conflict", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, "race-a", "rehydrated A"),
            pool.submit(worker, "race-b", "rehydrated B"),
        ]
        results = [future.result(timeout=30) for future in futures]

    outcomes = [item[0] for item in results]
    assert outcomes.count("ok") == 1, results
    assert outcomes.count("conflict") == 1, results


def test_pitch_history_survives_reload(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]

    enriched = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": "reload-enrich-1",
            "preparation_method_note": "rehydrated 15 minutes",
        },
    )
    assert enriched.status_code == 200, enriched.text

    with TestClient(app) as fresh_client:
        fresh_client.headers["Origin"] = "http://testserver"
        login = fresh_client.post(
            "/api/v1/auth/login",
            json={"username": "brewer", "password": "test-password-not-a-secret"},
        )
        assert login.status_code == 200
        fresh_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        history = fresh_client.get("/api/v1/fermentation-sessions/pitch-history")
        assert history.status_code == 200
        assert any(
            item["preparation_method_note"] == "rehydrated 15 minutes" for item in history.json()
        )


def test_history_rows_and_fk_integrity(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    lot_id, _ = create_ingredient_lot()

    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={"operation_id": str(uuid.uuid4()), "ingredient_lot_id": str(lot_id)},
    )
    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        reference = db.scalar(
            select(FermentationYeastPitchReference).where(
                FermentationYeastPitchReference.fermentation_session_id == uuid.UUID(session_id)
            )
        )
        assert reference is not None
        assert reference.ingredient_lot_id == lot_id
        assert reference.lot_snapshot.get("lot_code")
        history = list(
            db.scalars(
                select(FermentationYeastReferenceHistory).where(
                    FermentationYeastReferenceHistory.fermentation_session_id
                    == uuid.UUID(session_id)
                )
            ).all()
        )
        assert len(history) == 1
        assert history[0].new_snapshot["ingredient_lot_id"] == str(lot_id)


def test_foreign_session_source_returns_404(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]

    with SessionLocal() as db:
        other = User(
            username="yeast-foreign-source",
            password_hash=password_hash.hash("other-password-not-a-secret"),
        )
        db.add(other)
        db.commit()
        other_id = other.id

    foreign_session, foreign_ref = create_source_fermentation_session(owner_id=other_id)
    response = client.post(
        _YEAST_URL.format(session_id=session_id),
        json={
            "operation_id": str(uuid.uuid4()),
            "source_fermentation_session_id": str(foreign_session),
            "source_yeast_reference_id": str(foreign_ref),
        },
    )
    assert response.status_code == 404, response.text
