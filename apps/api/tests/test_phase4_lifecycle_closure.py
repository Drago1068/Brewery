"""Slice 3 PostgreSQL concurrency for lifecycle commands."""
# ruff: noqa: F811 - test parameters intentionally shadow the fixture import

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from phase4_fixtures import started_fermentation  # noqa: F401
from phase4_lifecycle_helpers import seed_stable_gravity_measurements
from sqlalchemy import select

from brewing_api.application.errors import ConflictError
from brewing_api.application.phase4.completion import (
    CompleteFermentationCommand,
    complete_fermentation,
)
from brewing_api.application.phase4.measurements import MeasurementCommand, record_measurement
from brewing_api.domain.fermentation.models import FermentationSession
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("TEST_USE_POSTGRES") != "1",
        reason="Slice 3 lifecycle concurrency requires PostgreSQL (TEST_USE_POSTGRES=1)",
    ),
]


_LATE_REASON = "Recorded after hydrometer reading was found in notebook from yesterday"


def _race_complete_vs_measurement(
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    stage_id: uuid.UUID,
    revision: int,
) -> list[tuple[str, object]]:
    barrier = threading.Barrier(2, timeout=10)

    def complete_worker() -> tuple[str, object]:
        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                assert user is not None
                barrier.wait()
                session, assessment = complete_fermentation(
                    db,
                    user,
                    session_id,
                    CompleteFermentationCommand(
                        operation_id="race-complete-a",
                        expected_revision=revision,
                        override=True,
                        override_reason="Owner override for concurrency race validation test",
                    ),
                )
                return ("ok", (session, assessment))
        except ConflictError as exc:
            return ("conflict", exc)
        except Exception as exc:  # noqa: BLE001
            return ("error", exc)

    def measure_worker() -> tuple[str, object]:
        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                assert user is not None
                barrier.wait()
                measurement = record_measurement(
                    db,
                    user,
                    session_id,
                    MeasurementCommand(
                        measurement_type="FERMENTATION_GRAVITY",
                        value=Decimal("1.020"),
                        unit="SG",
                        observed_at=datetime.now(UTC),
                        operation_id="race-measure-b",
                        stage_instance_id=stage_id,
                        method="HYDROMETER",
                        sample_temperature_c=Decimal("20"),
                        expected_revision=revision,
                    ),
                )
                return ("ok", measurement)
        except ConflictError as exc:
            return ("conflict", exc)
        except Exception as exc:  # noqa: BLE001
            return ("error", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(complete_worker), pool.submit(measure_worker)]
        return [future.result(timeout=30) for future in futures]


def test_concurrent_complete_vs_measurement_one_winner(started_fermentation):
    session_id = uuid.UUID(started_fermentation["fermentation_session_id"])
    stage_id = uuid.UUID(started_fermentation["active_stage_id"])
    seed_stable_gravity_measurements(
        fermentation_session_id=str(session_id),
        stage_instance_id=str(stage_id),
        values=("1.020", "1.020", "1.020"),
    )
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "brewer"))
        assert user is not None
        revision = db.get(FermentationSession, session_id).revision

    results = _race_complete_vs_measurement(
        user_id=user.id,
        session_id=session_id,
        stage_id=stage_id,
        revision=revision,
    )
    outcomes = [item[0] for item in results]
    assert outcomes.count("ok") == 1, results
    assert outcomes.count("conflict") == 1, results

    with SessionLocal() as db:
        session = db.get(FermentationSession, session_id)
        assert session.revision == revision + 1
