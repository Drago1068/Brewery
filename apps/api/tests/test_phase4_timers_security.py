"""Slice 4 security and PostgreSQL concurrency for timers/reminders."""
# ruff: noqa: F811 - test parameters intentionally shadow the fixture import

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from phase4_fixtures import started_fermentation  # noqa: F401
from sqlalchemy import select

from brewing_api.application.auth import password_hash
from brewing_api.application.errors import ConflictError
from brewing_api.application.phase4.reminders import acknowledge_reminder
from brewing_api.domain.fermentation.models import FermentationReminder
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal

pytestmark = pytest.mark.integration


def test_cross_user_timer_and_reminder_denied(started_fermentation, client):
    owner = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    detail = owner.get(f"/api/v1/fermentation-sessions/{session_id}")
    timer_id = detail.json()["timers"][0]["id"]
    reminder_id = detail.json()["reminders"][0]["id"]

    with SessionLocal() as db:
        db.add(
            User(
                username="other-timer-user",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "other-timer-user", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]

    pause = client.post(
        f"/api/v1/fermentation-sessions/timers/{timer_id}/pause",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert pause.status_code == 404, pause.text
    ack = client.post(
        f"/api/v1/fermentation-sessions/reminders/{reminder_id}/acknowledge",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert ack.status_code == 404, ack.text


@pytest.mark.skipif(
    os.environ.get("TEST_USE_POSTGRES") != "1",
    reason="Slice 4 concurrency requires PostgreSQL",
)
def test_concurrent_reminder_ack_one_history(started_fermentation):
    client = started_fermentation["client"]
    session_id = uuid.UUID(started_fermentation["fermentation_session_id"])
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    reminder_id = uuid.UUID(detail.json()["reminders"][0]["id"])
    revision = detail.json()["revision"]

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "brewer"))
        assert user is not None
        user_id = user.id

    barrier = threading.Barrier(2, timeout=10)

    def worker(operation_id: str):
        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                assert user is not None
                barrier.wait()
                return (
                    "ok",
                    acknowledge_reminder(
                        db,
                        user,
                        reminder_id,
                        operation_id=operation_id,
                        expected_revision=revision,
                    ),
                )
        except ConflictError as exc:
            return ("conflict", exc)
        except Exception as exc:  # noqa: BLE001
            return ("error", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result(timeout=30)
            for future in [
                pool.submit(worker, "ack-race-a"),
                pool.submit(worker, "ack-race-b"),
            ]
        ]
    outcomes = [item[0] for item in results]
    assert outcomes.count("ok") == 1, results
    assert outcomes.count("conflict") == 1, results
    with SessionLocal() as db:
        from brewing_api.domain.fermentation.models import FermentationReminderHistory

        history = list(
            db.scalars(
                select(FermentationReminderHistory).where(
                    FermentationReminderHistory.reminder_id == reminder_id,
                    FermentationReminderHistory.cause == "BREWER_ACK",
                )
            ).all()
        )
        reminder = db.get(FermentationReminder, reminder_id)
        assert reminder is not None
        assert reminder.status == "ACKNOWLEDGED"
        assert len(history) == 1
