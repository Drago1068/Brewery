"""P4-FR-037 pitch-rate estimate read model."""
# ruff: noqa: F811 - test parameters intentionally shadow the fixture import

from __future__ import annotations

import uuid
from decimal import Decimal

from calculations.brewing import yeast_pitch_cells
from phase4_fixtures import started_fermentation  # noqa: F401
from sqlalchemy import select

from brewing_api.domain.fermentation.models import (
    FermentationOgConsumption,
    FermentationPlanSnapshot,
    FermentationSession,
)
from brewing_api.platform.database import SessionLocal


def test_pitch_rate_not_computed_without_snapshot_inputs(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    body = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert body["pitch_rate_estimate"]["status"] == "NOT_COMPUTED"


def test_pitch_rate_calculated_when_snapshot_inputs_present(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    with SessionLocal() as db:
        snapshot = db.scalar(
            select(FermentationPlanSnapshot).where(
                FermentationPlanSnapshot.fermentation_session_id == uuid.UUID(session_id)
            )
        )
        assert snapshot is not None
        payload = dict(snapshot.payload)
        payload["recipe_snapshot"] = {
            "batch_size_liters": "20",
            "pitch_rate_million_per_ml_plato": "0.75",
        }
        snapshot.payload = payload
        db.commit()

    body = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    og = Decimal(body["og_consumption"]["consumed_value"])
    expected = yeast_pitch_cells(Decimal("20"), og, Decimal("0.75"))
    estimate = body["pitch_rate_estimate"]
    assert estimate["status"] == "CALCULATED"
    assert estimate["provenance"] == "CALCULATED"
    assert estimate["unit"] == "cells"
    assert Decimal(estimate["value"]) == expected


def test_pitch_rate_unit_compute_omits_missing_rate(started_fermentation):
    from brewing_api.application.phase4.pitch_rate import compute_pitch_rate_estimate

    with SessionLocal() as db:
        session = db.get(
            FermentationSession, uuid.UUID(started_fermentation["fermentation_session_id"])
        )
        snapshot = db.scalar(
            select(FermentationPlanSnapshot).where(
                FermentationPlanSnapshot.fermentation_session_id == session.id
            )
        )
        og = db.scalar(
            select(FermentationOgConsumption).where(
                FermentationOgConsumption.fermentation_session_id == session.id
            )
        )
        payload = dict(snapshot.payload)
        payload["recipe_snapshot"] = {"batch_size_liters": "20"}
        snapshot.payload = payload
        db.commit()
        result = compute_pitch_rate_estimate(db, session, snapshot=snapshot, og=og)
        assert result["status"] == "NOT_COMPUTED"
