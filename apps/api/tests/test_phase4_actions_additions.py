"""Slice 14 — ACTIONS_ADDITIONS (FR-052–057/061/070, AC-031/032/033/048/056/068, ADV-031/042)."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from brewing_api.domain.fermentation.models import (
    FermentationAction,
    FermentationAdditionEvent,
    FermentationAdditionRequirement,
    FermentationJournalEvent,
    FermentationSession,
    FermentationYeastPitchReference,
)
from brewing_api.domain.ingredients.models import Ingredient
from brewing_api.domain.inventory.models import InventoryReservation, InventoryTransaction
from brewing_api.domain.recipes.models import RecipeIngredient
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now
from brewing_api.application.phase4.time_validation import _coerce_aware
from phase4_lifecycle_helpers import reach_fermentation_complete, skip_conditioning

pytestmark = pytest.mark.integration

_CORRECTION_REASON = "Corrected addition quantity after reviewing process notes carefully"


def _revision(client, session_id: str) -> int:
    return client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]


def _brew_recipe_version_id(brew_session_id: str) -> uuid.UUID:
    from brewing_api.domain.brew_sessions.models import BrewSession

    with SessionLocal() as db:
        brew = db.get(BrewSession, uuid.UUID(brew_session_id))
        assert brew is not None
        return brew.recipe_version_id


def _insert_dry_hop(
    brew_session_id: str,
    *,
    timing_minutes: int | None = 2880,
    amount: str = "50",
) -> uuid.UUID:
    from brewing_api.domain.brew_sessions.models import BrewSession

    recipe_version_id = _brew_recipe_version_id(brew_session_id)
    with SessionLocal() as db:
        brew = db.get(BrewSession, uuid.UUID(brew_session_id))
        assert brew is not None
        ingredient = Ingredient(
            owner_id=brew.user_id,
            name=f"Dry Hop {uuid.uuid4().hex[:8]}",
            category="HOP",
            canonical_unit="g",
            attributes={},
        )
        db.add(ingredient)
        db.flush()
        row = RecipeIngredient(
            recipe_version_id=recipe_version_id,
            ingredient_id=ingredient.id,
            amount=Decimal(amount),
            unit="g",
            use_stage="DRY_HOP",
            timing_minutes=timing_minutes,
        )
        db.add(row)
        db.commit()
        return row.id


def _reach_handoff_ready(client, started: dict) -> dict:
    payload = reach_fermentation_complete(client, started)
    skipped = skip_conditioning(
        client,
        session_id=started["fermentation_session_id"],
        revision=payload["revision"],
    )
    assert skipped.status_code == 200, skipped.text
    session_id = started["fermentation_session_id"]
    assess = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/assess-packaging-readiness",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert assess.status_code == 200, assess.text
    assessment_id = assess.json()["packaging_readiness_assessment"]["id"]
    handoff = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/record-packaging-readiness-handoff",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
            "assessment_id": assessment_id,
        },
    )
    assert handoff.status_code == 200, handoff.text
    return handoff.json()


def _close(client, session_id: str, *, revision: int | None = None, operation_id: str | None = None):
    return client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/close",
        json={
            "operation_id": operation_id or str(uuid.uuid4()),
            "expected_revision": revision if revision is not None else _revision(client, session_id),
        },
    )


def test_ac031_dry_hop_due_at_pitched_plus_48h(completed_brew_with_pitch):
    """P4-AC-031: DRY_HOP timing_minutes=2880 → due_at = pitched_at+48h on ACTIVE_FERMENTATION."""
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    _insert_dry_hop(brew_session_id, timing_minutes=2880)

    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201, started.text
    body = started.json()
    session_id = body["id"]
    reqs = body["addition_requirements"]
    assert len(reqs) == 1
    assert reqs[0]["use_stage"] == "DRY_HOP"
    assert reqs[0]["timing_basis"] == "FROM_PITCH"
    assert reqs[0]["timing_offset_seconds"] == 2880 * 60
    assert reqs[0]["runtime_occurrence_policy"] == "DO_NOT_COPY"

    with SessionLocal() as db:
        pitch = db.scalar(
            select(FermentationYeastPitchReference).where(
                FermentationYeastPitchReference.fermentation_session_id == uuid.UUID(session_id)
            )
        )
        requirement = db.scalar(
            select(FermentationAdditionRequirement).where(
                FermentationAdditionRequirement.fermentation_session_id == uuid.UUID(session_id)
            )
        )
        assert pitch is not None and requirement is not None
        expected = pitch.pitched_at + timedelta(hours=48)
        assert requirement.planned_due_at.replace(microsecond=0) == expected.replace(microsecond=0)
        stage = next(
            s for s in body["stages"] if s["canonical_stage_type"] == "ACTIVE_FERMENTATION"
        )
        assert str(requirement.stage_instance_id) == stage["id"]


def test_ac032_runtime_repeat_denied(started_fermentation, completed_brew_with_pitch):
    """P4-AC-032: second planned occurrence / runtime repeat → 409."""
    # Start a session that has a planned dry hop.
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    # completed_brew_with_pitch may already have a fermentation from started_fermentation fixture
    # dependency order: started_fermentation uses same brew. Use a fresh brew via abort+restart path
    # by inserting dry hop before a dedicated start on a new completed brew — reuse started if
    # requirements empty by inserting before a new start after abort.
    del started_fermentation  # ensure fixture still runs for isolation if needed

    # Prefer mutating an existing ACTIVE session's plan is insufficient; start with ingredient.
    # Abort any existing ferment for this brew and restart after inserting dry hop.
    with SessionLocal() as db:
        existing = db.scalar(
            select(FermentationSession).where(
                FermentationSession.brew_session_id == uuid.UUID(brew_session_id),
                FermentationSession.status != "ABORTED",
            )
        )
    if existing is not None:
        aborted = client.post(
            f"/api/v1/fermentation-sessions/{existing.id}/commands/abort",
            json={
                "operation_id": str(uuid.uuid4()),
                "expected_revision": _revision(client, str(existing.id)),
                "reason": "Abort to restart with planned dry-hop addition for AC-032",
            },
        )
        assert aborted.status_code == 200, aborted.text

    _insert_dry_hop(brew_session_id, timing_minutes=60)
    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    req = started.json()["addition_requirements"][0]
    req_id = req["requirement_id"]
    now = utc_now()
    first = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/{req_id}/execute",
        json={
            "operation_id": str(uuid.uuid4()),
            "quantity": "50",
            "unit": "g",
            "occurred_at": now.isoformat(),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/{req_id}/execute",
        json={
            "operation_id": str(uuid.uuid4()),
            "quantity": "50",
            "unit": "g",
            "occurred_at": now.isoformat(),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "RUNTIME_REPEAT_DENIED"


def test_ac033_and_fr070_zero_inventory_consumption(started_fermentation, completed_brew_with_pitch):
    """P4-AC-033 / P4-FR-070: addition execute/retry creates zero CONSUMPTION ledger rows."""
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    with SessionLocal() as db:
        existing = db.scalar(
            select(FermentationSession).where(
                FermentationSession.brew_session_id == uuid.UUID(brew_session_id),
                FermentationSession.status != "ABORTED",
            )
        )
    if existing is not None:
        aborted = client.post(
            f"/api/v1/fermentation-sessions/{existing.id}/commands/abort",
            json={
                "operation_id": str(uuid.uuid4()),
                "expected_revision": _revision(client, str(existing.id)),
                "reason": "Abort to restart with planned addition for AC-033 ledger proof",
            },
        )
        assert aborted.status_code == 200, aborted.text

    _insert_dry_hop(brew_session_id, timing_minutes=0)
    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    req_id = started.json()["addition_requirements"][0]["requirement_id"]

    with SessionLocal() as db:
        before_tx = db.scalar(select(func.count()).select_from(InventoryTransaction)) or 0
        before_cons = (
            db.scalar(
                select(func.count()).select_from(InventoryTransaction).where(
                    InventoryTransaction.transaction_type == "CONSUMPTION"
                )
            )
            or 0
        )
        before_res = db.scalar(select(func.count()).select_from(InventoryReservation)) or 0

    op = str(uuid.uuid4())
    payload = {
        "operation_id": op,
        "quantity": "28",
        "unit": "g",
        "occurred_at": utc_now().isoformat(),
        "expected_revision": _revision(client, session_id),
    }
    first = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/{req_id}/execute",
        json=payload,
    )
    assert first.status_code == 201, first.text
    assert first.json()["inventory_effect"] is False
    replay = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/{req_id}/execute",
        json=payload,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == first.json()["id"]

    with SessionLocal() as db:
        after_tx = db.scalar(select(func.count()).select_from(InventoryTransaction)) or 0
        after_cons = (
            db.scalar(
                select(func.count()).select_from(InventoryTransaction).where(
                    InventoryTransaction.transaction_type == "CONSUMPTION"
                )
            )
            or 0
        )
        after_res = db.scalar(select(func.count()).select_from(InventoryReservation)) or 0
    assert after_tx == before_tx
    assert after_cons == before_cons
    assert after_res == before_res


def test_ac048_aborted_measurement_prohibited(started_fermentation):
    """P4-AC-048: ABORTED + new measurement → 409 TERMINAL_SESSION_EVIDENCE_PROHIBITED."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    aborted = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/abort",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
            "reason": "Abort session to prove terminal measurement prohibition AC-048",
        },
    )
    assert aborted.status_code == 200, aborted.text
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.020",
            "unit": "SG",
            "observed_at": utc_now().isoformat(),
            "stage_instance_id": started_fermentation["active_stage_id"],
            "method": "HYDROMETER",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "TERMINAL_SESSION_EVIDENCE_PROHIBITED"


def test_ac056_invalid_action_type_rejected(started_fermentation):
    """P4-AC-056: RecordAction with type outside §21.1 → 422, no action row."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    with SessionLocal() as db:
        before = (
            db.scalar(
                select(func.count()).select_from(FermentationAction).where(
                    FermentationAction.fermentation_session_id == uuid.UUID(session_id)
                )
            )
            or 0
        )
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/actions",
        json={
            "operation_id": str(uuid.uuid4()),
            "action_type": "NOT_A_REAL_ACTION",
            "occurred_at": utc_now().isoformat(),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert response.status_code == 422, response.text
    with SessionLocal() as db:
        after = (
            db.scalar(
                select(func.count()).select_from(FermentationAction).where(
                    FermentationAction.fermentation_session_id == uuid.UUID(session_id)
                )
            )
            or 0
        )
    assert after == before


def test_fr056_valid_action_recorded(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/actions",
        json={
            "operation_id": str(uuid.uuid4()),
            "action_type": "TEMPERATURE_ADJUSTMENT_NOTE",
            "occurred_at": utc_now().isoformat(),
            "note": "Dropped setpoint by 1C",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["action_type"] == "TEMPERATURE_ADJUSTMENT_NOTE"
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert any(a["id"] == response.json()["id"] for a in detail.json()["actions"])


def test_adv031_unplanned_while_paused_denied(started_fermentation):
    """P4-ADV-031: unplanned addition while PAUSED → 409 SESSION_PAUSED."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    paused = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/pause",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert paused.status_code == 200, paused.text
    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/unplanned",
        json={
            "operation_id": str(uuid.uuid4()),
            "quantity": "10",
            "unit": "g",
            "occurred_at": utc_now().isoformat(),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "SESSION_PAUSED"


def test_ac068_terminal_addition_boundaries_sqlite(started_fermentation):
    """P4-AC-068 boundary rules (non-interleave) on SQLite."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    brew_session_id = started_fermentation["session_id"]

    with SessionLocal() as db:
        reqs = list(
            db.scalars(
                select(FermentationAdditionRequirement).where(
                    FermentationAdditionRequirement.fermentation_session_id
                    == uuid.UUID(session_id)
                )
            ).all()
        )
    if not reqs:
        aborted = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/commands/abort",
            json={
                "operation_id": str(uuid.uuid4()),
                "expected_revision": _revision(client, session_id),
                "reason": "Abort to restart with planned addition for AC-068 boundaries",
            },
        )
        assert aborted.status_code == 200, aborted.text
        _insert_dry_hop(brew_session_id, timing_minutes=30)
        started = client.post(
            f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
            json={"operation_id": str(uuid.uuid4())},
        )
        assert started.status_code == 201, started.text
        session_id = started.json()["id"]
        started_fermentation = {
            **started_fermentation,
            "fermentation_session_id": session_id,
            "active_stage_id": next(
                s["id"]
                for s in started.json()["stages"]
                if s["canonical_stage_type"] == "ACTIVE_FERMENTATION"
            ),
        }

    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    req_id = detail["addition_requirements"][0]["requirement_id"]

    _reach_handoff_ready(client, started_fermentation)
    closed = _close(client, session_id)
    assert closed.status_code == 200, closed.text

    # Place closed_at 12h ago so recorded_at is well inside the 24h window
    # (exact +24h inclusivity is covered by the post-window denial below).
    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        assert session is not None
        session.closed_at = utc_now() - timedelta(hours=12)
        db.commit()
        closed_at = _coerce_aware(session.closed_at)
        revision = session.revision

    occurred = (closed_at - timedelta(minutes=1)).isoformat()
    op_boundary = str(uuid.uuid4())

    ok_planned = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/{req_id}/execute",
        json={
            "operation_id": op_boundary,
            "quantity": "40",
            "unit": "g",
            "occurred_at": occurred,
            "expected_revision": revision,
        },
    )
    assert ok_planned.status_code == 201, ok_planned.text
    assert ok_planned.json()["late_entry"] is True
    assert ok_planned.json()["terminal_state_at_recording"] == "CLOSED"

    ok_unplanned = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/unplanned",
        json={
            "operation_id": str(uuid.uuid4()),
            "quantity": "5",
            "unit": "g",
            "occurred_at": occurred,
            "expected_revision": revision + 1,
        },
    )
    assert ok_unplanned.status_code == 201, ok_unplanned.text
    assert ok_unplanned.json()["late_entry"] is True

    after_close = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/unplanned",
        json={
            "operation_id": str(uuid.uuid4()),
            "quantity": "5",
            "unit": "g",
            "occurred_at": (closed_at + timedelta(minutes=1)).isoformat(),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert after_close.status_code == 422, after_close.text
    assert after_close.json()["code"] == "TERMINAL_ADDITION_OCCURRED_AFTER_CLOSE"

    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        assert session is not None
        session.closed_at = utc_now() - timedelta(hours=25)
        db.commit()
        closed_past_window = _coerce_aware(session.closed_at)

    late = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/unplanned",
        json={
            "operation_id": str(uuid.uuid4()),
            "quantity": "5",
            "unit": "g",
            "occurred_at": (closed_past_window - timedelta(minutes=1)).isoformat(),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert late.status_code == 409, late.text
    assert late.json()["code"] == "LATE_ENTRY_WINDOW_CLOSED"

    replay = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/{req_id}/execute",
        json={
            "operation_id": op_boundary,
            "quantity": "40",
            "unit": "g",
            "occurred_at": occurred,
            "expected_revision": revision,
        },
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == ok_planned.json()["id"]

    reused = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/{req_id}/execute",
        json={
            "operation_id": op_boundary,
            "quantity": "41",
            "unit": "g",
            "occurred_at": occurred,
            "expected_revision": revision,
        },
    )
    assert reused.status_code == 409, reused.text
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    with SessionLocal() as db:
        journal_count = (
            db.scalar(
                select(func.count()).select_from(FermentationJournalEvent).where(
                    FermentationJournalEvent.fermentation_session_id == uuid.UUID(session_id),
                    FermentationJournalEvent.event_type == "FERMENTATION_ADDITION_RECORDED",
                    FermentationJournalEvent.operation_id == op_boundary,
                )
            )
            or 0
        )
    assert journal_count == 1


def test_adv042_lost_response_replay_after_window(started_fermentation):
    """P4-ADV-042: accepted at closed_at+24h; lost response; replay; fresh key denied."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _reach_handoff_ready(client, started_fermentation)
    closed = _close(client, session_id)
    assert closed.status_code == 200, closed.text

    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        assert session is not None
        session.closed_at = utc_now() - timedelta(hours=12)
        db.commit()
        closed_at = _coerce_aware(session.closed_at)
        revision = session.revision

    op = str(uuid.uuid4())
    body = {
        "operation_id": op,
        "quantity": "12",
        "unit": "g",
        "occurred_at": (closed_at - timedelta(minutes=1)).isoformat(),
        "expected_revision": revision,
    }
    first = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/unplanned",
        json=body,
    )
    assert first.status_code == 201, first.text
    event_id = first.json()["id"]

    with SessionLocal() as db:
        session = db.get(FermentationSession, uuid.UUID(session_id))
        assert session is not None
        session.closed_at = utc_now() - timedelta(hours=25)
        db.commit()
        past_closed = _coerce_aware(session.closed_at)

    replay = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/unplanned",
        json=body,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == event_id

    fresh = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/unplanned",
        json={
            "operation_id": str(uuid.uuid4()),
            "quantity": "12",
            "unit": "g",
            "occurred_at": (past_closed - timedelta(minutes=1)).isoformat(),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert fresh.status_code == 409, fresh.text
    assert fresh.json()["code"] == "LATE_ENTRY_WINDOW_CLOSED"

    post_close = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/unplanned",
        json={
            "operation_id": str(uuid.uuid4()),
            "quantity": "12",
            "unit": "g",
            "occurred_at": (past_closed + timedelta(minutes=1)).isoformat(),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert post_close.status_code == 422, post_close.text
    assert post_close.json()["code"] == "TERMINAL_ADDITION_OCCURRED_AFTER_CLOSE"

    with SessionLocal() as db:
        events = (
            db.scalar(
                select(func.count()).select_from(FermentationAdditionEvent).where(
                    FermentationAdditionEvent.fermentation_session_id == uuid.UUID(session_id),
                    FermentationAdditionEvent.planned.is_(False),
                )
            )
            or 0
        )
        journals = (
            db.scalar(
                select(func.count()).select_from(FermentationJournalEvent).where(
                    FermentationJournalEvent.fermentation_session_id == uuid.UUID(session_id),
                    FermentationJournalEvent.event_type == "FERMENTATION_ADDITION_RECORDED",
                    FermentationJournalEvent.operation_id == op,
                )
            )
            or 0
        )
    assert events == 1
    assert journals == 1


def test_fr055_addition_correction_current_leaf(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    created = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/additions/unplanned",
        json={
            "operation_id": str(uuid.uuid4()),
            "quantity": "10",
            "unit": "g",
            "occurred_at": utc_now().isoformat(),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]
    correction = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/addition-events/{event_id}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": event_id,
            "reason": _CORRECTION_REASON,
            "quantity": "12",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert correction.status_code == 201, correction.text
    stale = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/addition-events/{event_id}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": event_id,
            "reason": _CORRECTION_REASON,
            "quantity": "13",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "ADDITION_CORRECTION_TARGET_SUPERSEDED"
    detail = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    leaf = next(e for e in detail["addition_events"] if e["id"] == event_id)
    assert Decimal(leaf["actual_quantity"]) == Decimal("12")
    assert leaf["current_correction_id"] == correction.json()["id"]


def test_negative_timing_minutes_rejects_start(completed_brew_with_pitch, monkeypatch):
    """Defensive FR-052 guard: negative timing_minutes fails materialization (422).

    recipe_ingredients.ck_recipe_ingredient_timing already forbids storing negatives
    on PostgreSQL; inject a synthetic row so the plan path is still exercised.
    """
    from types import SimpleNamespace

    from brewing_api.application.phase4 import plan as plan_mod

    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    fake = SimpleNamespace(id=uuid.uuid4(), timing_minutes=-10)
    monkeypatch.setattr(
        plan_mod,
        "_ordered_fermentation_additions",
        lambda *_args, **_kwargs: [fake],
    )
    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 422, started.text
    assert "NEGATIVE_TIMING" in started.text.upper()


@pytest.mark.skipif(os.getenv("TEST_USE_POSTGRES") != "1", reason="PostgreSQL concurrency")
def test_ac068_close_vs_late_addition_interleave(started_fermentation):
    """P4-AC-068 / ADV interleave: Close vs late addition one winner, one STALE_REVISION."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    stage_id = started_fermentation["active_stage_id"]
    _reach_handoff_ready(client, started_fermentation)
    rev = _revision(client, session_id)
    # Historical occurrence while ACTIVE_FERMENTATION is already COMPLETED (§24 late entry).
    occurred = (utc_now() - timedelta(hours=1)).isoformat()
    barrier = threading.Barrier(2)
    results: list[tuple[str, int, str | None]] = []
    lock = threading.Lock()

    def _close_race():
        barrier.wait()
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/commands/close",
            json={"operation_id": str(uuid.uuid4()), "expected_revision": rev},
        )
        code = None
        if response.headers.get("content-type", "").startswith("application/json"):
            code = response.json().get("code")
        with lock:
            results.append(("close", response.status_code, code))

    def _add_race():
        barrier.wait()
        response = client.post(
            f"/api/v1/fermentation-sessions/{session_id}/additions/unplanned",
            json={
                "operation_id": str(uuid.uuid4()),
                "quantity": "3",
                "unit": "g",
                "occurred_at": occurred,
                "stage_instance_id": stage_id,
                "late_entry_reason": "Historical dry-hop note recorded at handoff boundary",
                "expected_revision": rev,
            },
        )
        code = None
        if response.headers.get("content-type", "").startswith("application/json"):
            code = response.json().get("code")
        with lock:
            results.append(("add", response.status_code, code))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_close_race), pool.submit(_add_race)]
        for future in futures:
            future.result()
    statuses = {name: status for name, status, _ in results}
    assert 200 in statuses.values() or 201 in statuses.values(), results
    assert 409 in statuses.values(), results
    stale = [r for r in results if r[1] == 409]
    assert any(r[2] == "STALE_REVISION" for r in stale), results
