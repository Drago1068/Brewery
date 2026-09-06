"""Slice 7 — unknown OG entry and ReconcileUpstreamOriginalGravity."""

from __future__ import annotations

import os
import threading
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from brewing_api.application.phase4.og_consumption import (
    ReconcileOgCommand,
    current_og_consumption,
    reconcile_upstream_original_gravity,
)
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage
from brewing_api.domain.fermentation.models import FermentationOgConsumption
from brewing_api.domain.identity.models import User
from brewing_api.domain.measurements.models import Measurement
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now
from phase4_fixtures import _measurement

pytestmark = pytest.mark.integration


@pytest.fixture
def completed_brew_without_og(active_mash):
    """Completed brew with pitch handoff but no ORIGINAL_GRAVITY leaf (waived/absent).

    Leaves an ACTIVE POST_BOIL stage so a later Phase 3 OG leaf can still be recorded
    for ReconcileUpstreamOriginalGravity without fabricating OG at start.
    """
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    command = active_mash["command"]

    for kind, value, unit in [("MASH_PH", "5.30", "pH"), ("MASH_GRAVITY", "1.048", "SG")]:
        response = client.post(
            f"/api/v1/brew-sessions/stages/{stage_id}/measurements",
            json=_measurement(kind, value, unit),
        )
        assert response.status_code == 201, response.text

    post_boil_id = uuid.uuid4()
    with SessionLocal() as db:
        session = db.get(BrewSession, uuid.UUID(session_id))
        assert session is not None
        now = utc_now()
        db.add(
            BrewStage(
                id=post_boil_id,
                brew_session_id=session.id,
                name="POST_BOIL",
                canonical_stage_type="POST_BOIL",
                status="ACTIVE",
                started_at=now,
                target_duration_seconds=3600,
                target_temperature=session.target_mash_temperature,
                temperature_unit=session.mash_temperature_unit,
                target_ph=session.target_mash_ph,
                ph_tolerance=session.mash_ph_tolerance,
                target_gravity=session.target_mash_gravity,
                gravity_tolerance=session.mash_gravity_tolerance,
            )
        )
        db.commit()

    pitch = client.post(
        f"/api/v1/brew-sessions/{session_id}/pitch-handoff",
        json=command(
            yeast_addition_note="US-05 dry yeast pitched",
            pitch_temperature_c="18.0",
        ),
    )
    assert pitch.status_code == 201, pitch.text

    completed = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/complete",
        json=command(),
    )
    assert completed.status_code == 200, completed.text
    return {
        "client": client,
        "session_id": session_id,
        "pitch_handoff_id": pitch.json()["id"],
        "command": command,
        "mash_stage_id": stage_id,
        "post_boil_stage_id": str(post_boil_id),
    }


def test_start_with_unknown_og_fr004_adv021(completed_brew_without_og):
    """P4-FR-004 / P4-ADV-021: start without OG → UNKNOWN; ferment gravity is not OG."""
    client = completed_brew_without_og["client"]
    brew_id = completed_brew_without_og["session_id"]

    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201, started.text
    body = started.json()
    og = body["og_consumption"]
    assert og is not None
    assert og["og_availability"] == "UNKNOWN"
    assert og["brew_measurement_id"] is None
    assert og["consumed_value"] is None
    assert og["is_current"] is True

    active = next(
        s for s in body["stages"] if s["canonical_stage_type"] == "ACTIVE_FERMENTATION"
    )
    observed = utc_now().isoformat().replace("+00:00", "Z")
    gravity = client.post(
        f"/api/v1/fermentation-sessions/{body['id']}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.020",
            "unit": "SG",
            "observed_at": observed,
            "stage_instance_id": active["id"],
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
        },
    )
    assert gravity.status_code == 201, gravity.text

    detail = client.get(f"/api/v1/fermentation-sessions/{body['id']}")
    assert detail.status_code == 200
    refreshed = detail.json()
    assert refreshed["og_consumption"]["og_availability"] == "UNKNOWN"
    assert refreshed["og_consumption"]["brew_measurement_id"] is None
    assert all(
        item["measurement_type"] != "ORIGINAL_GRAVITY" for item in refreshed["measurements"]
    )
    assert refreshed["pitch_rate_estimate"]["status"] == "NOT_COMPUTED"

    with SessionLocal() as db:
        pins = list(
            db.scalars(
                select(FermentationOgConsumption).where(
                    FermentationOgConsumption.fermentation_session_id == uuid.UUID(body["id"])
                )
            ).all()
        )
        assert len(pins) == 1
        assert pins[0].og_availability == "UNKNOWN"
        assert pins[0].brew_measurement_id is None


def test_ac010_reconcile_after_phase3_og_correction(completed_brew_with_pitch):
    """P4-AC-010 / P4-FR-005: Phase 3 correction does not change pin until reconcile."""
    client = completed_brew_with_pitch["client"]
    brew_id = completed_brew_with_pitch["session_id"]
    original_og_id = completed_brew_with_pitch["og_measurement_id"]

    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201, started.text
    ferm_id = started.json()["id"]
    pin_before = started.json()["og_consumption"]
    assert pin_before["og_availability"] == "KNOWN"
    assert pin_before["brew_measurement_id"] == original_og_id
    revision = started.json()["revision"]

    correction = client.post(
        f"/api/v1/brew-sessions/measurements/{original_og_id}/corrections",
        json=_measurement("ORIGINAL_GRAVITY", "1.055", "SG", note="Phase 3 OG correction"),
    )
    assert correction.status_code == 201, correction.text
    corrected_id = correction.json()["id"]
    assert correction.json()["correction_of_id"] == original_og_id

    detail = client.get(f"/api/v1/fermentation-sessions/{ferm_id}")
    assert detail.status_code == 200
    still = detail.json()["og_consumption"]
    assert still["brew_measurement_id"] == original_og_id
    assert Decimal(still["consumed_value"]) == Decimal("1.052")

    with SessionLocal() as db:
        phase3_original = db.get(Measurement, uuid.UUID(original_og_id))
        assert phase3_original is not None
        assert Decimal(str(phase3_original.value)) == Decimal("1.052")
        phase3_correction = db.get(Measurement, uuid.UUID(corrected_id))
        assert phase3_correction is not None
        assert Decimal(str(phase3_correction.value)) == Decimal("1.055")

    op_id = str(uuid.uuid4())
    reconciled = client.post(
        f"/api/v1/fermentation-sessions/{ferm_id}/og-consumption",
        json={
            "operation_id": op_id,
            "brew_measurement_id": corrected_id,
            "expected_revision": revision,
        },
    )
    assert reconciled.status_code == 200, reconciled.text
    new_pin = reconciled.json()["og_consumption"]
    assert new_pin["og_availability"] == "KNOWN"
    assert new_pin["brew_measurement_id"] == corrected_id
    assert Decimal(new_pin["consumed_value"]) == Decimal("1.055")
    assert new_pin["pin_ordinal"] == 2
    assert new_pin["is_current"] is True

    session_body = reconciled.json()["session"]
    assert session_body["og_consumption"]["brew_measurement_id"] == corrected_id

    with SessionLocal() as db:
        pins = list(
            db.scalars(
                select(FermentationOgConsumption)
                .where(
                    FermentationOgConsumption.fermentation_session_id == uuid.UUID(ferm_id)
                )
                .order_by(FermentationOgConsumption.pin_ordinal)
            ).all()
        )
        assert len(pins) == 2
        assert pins[0].is_current is False
        assert str(pins[0].brew_measurement_id) == original_og_id
        assert pins[1].is_current is True
        assert str(pins[1].brew_measurement_id) == corrected_id
        phase3_original = db.get(Measurement, uuid.UUID(original_og_id))
        assert Decimal(str(phase3_original.value)) == Decimal("1.052")

    replay = client.post(
        f"/api/v1/fermentation-sessions/{ferm_id}/og-consumption",
        json={
            "operation_id": op_id,
            "brew_measurement_id": corrected_id,
            "expected_revision": revision,
        },
    )
    assert replay.status_code == 200
    assert replay.json()["og_consumption"]["id"] == new_pin["id"]


def test_reconcile_unknown_then_later_og(completed_brew_without_og):
    """FR-005 path: UNKNOWN start, later Phase 3 OG recorded, then reconcile."""
    client = completed_brew_without_og["client"]
    brew_id = completed_brew_without_og["session_id"]
    post_boil_id = completed_brew_without_og["post_boil_stage_id"]

    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201, started.text
    ferm_id = started.json()["id"]
    revision = started.json()["revision"]
    assert started.json()["og_consumption"]["og_availability"] == "UNKNOWN"

    # Brew session is COMPLETED after mash complete; late-entry on completed POST_BOIL.
    with SessionLocal() as db:
        stage = db.get(BrewStage, uuid.UUID(post_boil_id))
        assert stage is not None
        stage.status = "COMPLETED"
        stage.completed_at = utc_now()
        db.commit()

    og = client.post(
        f"/api/v1/brew-sessions/stages/{post_boil_id}/measurements",
        json=_measurement(
            "ORIGINAL_GRAVITY",
            "1.048",
            "SG",
            late_entry_reason="Authoritative OG available after fermentation start",
        ),
    )
    assert og.status_code == 201, og.text
    og_id = og.json()["id"]

    reconciled = client.post(
        f"/api/v1/fermentation-sessions/{ferm_id}/og-consumption",
        json={
            "operation_id": str(uuid.uuid4()),
            "brew_measurement_id": og_id,
            "expected_revision": revision,
        },
    )
    assert reconciled.status_code == 200, reconciled.text
    pin = reconciled.json()["og_consumption"]
    assert pin["og_availability"] == "KNOWN"
    assert pin["brew_measurement_id"] == og_id
    assert pin["pin_ordinal"] == 2


def test_reconcile_security_cross_session_and_mass_assignment(completed_brew_with_pitch):
    """Security: forged/cross-session leaf, mass assignment, stale revision.

    Uses a single brew fixture (shared active_mash cannot back two completed brews).
    Cross-session is exercised via a measurement ID that does not belong to this brew.
    """
    client = completed_brew_with_pitch["client"]
    brew_a = completed_brew_with_pitch["session_id"]
    og_a = completed_brew_with_pitch["og_measurement_id"]

    started_a = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_a}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started_a.status_code == 201
    ferm_a = started_a.json()["id"]
    rev_a = started_a.json()["revision"]

    # Foreign / forged measurement → 404 nondisclosure
    forged = client.post(
        f"/api/v1/fermentation-sessions/{ferm_a}/og-consumption",
        json={
            "operation_id": str(uuid.uuid4()),
            "brew_measurement_id": str(uuid.uuid4()),
            "expected_revision": rev_a,
        },
    )
    assert forged.status_code == 404

    # Mass assignment / unknown field
    bad = client.post(
        f"/api/v1/fermentation-sessions/{ferm_a}/og-consumption",
        json={
            "operation_id": str(uuid.uuid4()),
            "brew_measurement_id": og_a,
            "expected_revision": rev_a,
            "og_availability": "KNOWN",
            "status": "CLOSED",
        },
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "UNKNOWN_FIELD"
    stale = client.post(
        f"/api/v1/fermentation-sessions/{ferm_a}/og-consumption",
        json={
            "operation_id": str(uuid.uuid4()),
            "brew_measurement_id": og_a,
            "expected_revision": 9999,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_REVISION"


def test_reconcile_idempotency_key_reuse_conflict(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_id = completed_brew_with_pitch["session_id"]
    og_id = completed_brew_with_pitch["og_measurement_id"]
    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    ferm_id = started.json()["id"]
    revision = started.json()["revision"]

    correction = client.post(
        f"/api/v1/brew-sessions/measurements/{og_id}/corrections",
        json=_measurement("ORIGINAL_GRAVITY", "1.054", "SG"),
    )
    corrected_id = correction.json()["id"]
    op = str(uuid.uuid4())
    first = client.post(
        f"/api/v1/fermentation-sessions/{ferm_id}/og-consumption",
        json={
            "operation_id": op,
            "brew_measurement_id": corrected_id,
            "expected_revision": revision,
        },
    )
    assert first.status_code == 200

    conflict = client.post(
        f"/api/v1/fermentation-sessions/{ferm_id}/og-consumption",
        json={
            "operation_id": op,
            "brew_measurement_id": og_id,
            "expected_revision": revision,
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_recovery_after_reconcile_reread(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_id = completed_brew_with_pitch["session_id"]
    og_id = completed_brew_with_pitch["og_measurement_id"]
    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    ferm_id = started.json()["id"]
    revision = started.json()["revision"]
    correction = client.post(
        f"/api/v1/brew-sessions/measurements/{og_id}/corrections",
        json=_measurement("ORIGINAL_GRAVITY", "1.053", "SG"),
    )
    corrected_id = correction.json()["id"]
    client.post(
        f"/api/v1/fermentation-sessions/{ferm_id}/og-consumption",
        json={
            "operation_id": str(uuid.uuid4()),
            "brew_measurement_id": corrected_id,
            "expected_revision": revision,
        },
    )
    # Fresh client reconstruction from PostgreSQL/SQLite persistence
    detail = client.get(f"/api/v1/fermentation-sessions/{ferm_id}")
    assert detail.status_code == 200
    assert detail.json()["og_consumption"]["brew_measurement_id"] == corrected_id
    assert detail.json()["og_consumption"]["og_availability"] == "KNOWN"


@pytest.mark.skipif(
    os.environ.get("TEST_USE_POSTGRES") != "1",
    reason="Slice 7 concurrency requires PostgreSQL",
)
def test_concurrent_reconcile_one_winner(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_id = completed_brew_with_pitch["session_id"]
    og_id = completed_brew_with_pitch["og_measurement_id"]
    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    session_id = uuid.UUID(started.json()["id"])
    revision = started.json()["revision"]
    correction = client.post(
        f"/api/v1/brew-sessions/measurements/{og_id}/corrections",
        json=_measurement("ORIGINAL_GRAVITY", "1.056", "SG"),
    )
    corrected_id = uuid.UUID(correction.json()["id"])

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "brewer"))
        assert user is not None
        user_id = user.id

    barrier = threading.Barrier(2, timeout=10)
    results: list[tuple] = []

    def worker(operation_id: str):
        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                assert user is not None
                barrier.wait()
                row = reconcile_upstream_original_gravity(
                    db,
                    user,
                    session_id,
                    ReconcileOgCommand(
                        operation_id=operation_id,
                        brew_measurement_id=corrected_id,
                        expected_revision=revision,
                    ),
                )
                return ("ok", row.pin_ordinal, str(row.id))
        except Exception as exc:  # noqa: BLE001 — capture race loser
            return ("err", type(exc).__name__, str(getattr(exc, "code", exc)))

    t1 = threading.Thread(target=lambda: results.append(worker(str(uuid.uuid4()))))
    t2 = threading.Thread(target=lambda: results.append(worker(str(uuid.uuid4()))))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert len(results) == 2
    oks = [r for r in results if r[0] == "ok"]
    errs = [r for r in results if r[0] == "err"]
    assert len(oks) == 1
    assert len(errs) == 1
    with SessionLocal() as db:
        current = current_og_consumption(db, session_id)
        assert current is not None
        assert current.is_current is True
        assert current.pin_ordinal == 2
        currents = list(
            db.scalars(
                select(FermentationOgConsumption).where(
                    FermentationOgConsumption.fermentation_session_id == session_id,
                    FermentationOgConsumption.is_current.is_(True),
                )
            ).all()
        )
        assert len(currents) == 1
