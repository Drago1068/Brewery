"""Slice 8 — P4-FR-036 / P4-AC-021 calculation read-model closure."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from calculations.fermentation import (
    CALCULATION_UNDEFINED,
    fermentation_progress,
    try_abv_percent,
    try_apparent_attenuation_ratio,
)
from sqlalchemy import select

from brewing_api.application.auth import password_hash
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage
from brewing_api.domain.fermentation.models import FermentationDerivedGravitySnapshot
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now
from phase4_fixtures import _measurement

pytestmark = pytest.mark.integration


def _gravity_payload(
    started: dict,
    *,
    value: str,
    observed_at: datetime | None = None,
) -> dict:
    when = observed_at or datetime.now(timezone.utc)
    return {
        "operation_id": str(uuid.uuid4()),
        "measurement_type": "FERMENTATION_GRAVITY",
        "value": value,
        "unit": "SG",
        "observed_at": when.isoformat(),
        "stage_instance_id": started["active_stage_id"],
        "method": "HYDROMETER",
        "sample_temperature_c": "20.00",
        "source": "OBSERVED",
    }


@pytest.fixture
def completed_brew_without_og(active_mash):
    """Completed brew with pitch but no ORIGINAL_GRAVITY leaf."""
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
    return {"client": client, "session_id": session_id}


def test_ac021_domain_goldens_attenuation_progress_abv():
    """P4-AC-021 domain goldens for attenuation / progress / ABV adapters."""
    assert try_apparent_attenuation_ratio(Decimal("1.050"), Decimal("1.010")) == Decimal("0.8")
    assert (
        try_apparent_attenuation_ratio(Decimal("1.050"), Decimal("0.990"))
        == CALCULATION_UNDEFINED
    )
    assert try_apparent_attenuation_ratio(None, Decimal("1.010")) == CALCULATION_UNDEFINED

    assert fermentation_progress(
        Decimal("1.050"), Decimal("1.030"), Decimal("1.010")
    ) == Decimal("0.5")
    assert fermentation_progress(
        Decimal("1.050"), Decimal("1.060"), Decimal("1.010")
    ) == Decimal("0")
    assert fermentation_progress(
        Decimal("1.050"), Decimal("1.000"), Decimal("1.010")
    ) == Decimal("1")
    assert (
        fermentation_progress(Decimal("1.050"), Decimal("1.030"), Decimal("1.050"))
        == CALCULATION_UNDEFINED
    )
    assert fermentation_progress(None, Decimal("1.030"), Decimal("1.010")) == CALCULATION_UNDEFINED

    assert try_abv_percent(Decimal("1.050"), Decimal("1.010")) == Decimal("5.25")
    assert try_abv_percent(Decimal("1.050"), Decimal("0.990")) == Decimal("7.875")
    assert try_abv_percent(Decimal("1.010"), Decimal("1.050")) == CALCULATION_UNDEFINED
    assert try_abv_percent(None, Decimal("1.010")) == CALCULATION_UNDEFINED
    assert try_abv_percent(Decimal("1.050"), None) == CALCULATION_UNDEFINED


def test_ac021_abv_exposed_on_session_read_model(started_fermentation):
    """P4-FR-036 / P4-AC-021: ABV from authoritative OG+FG via derived read model."""
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    og = Decimal("1.052")

    response = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(started_fermentation, value="1.012"),
    )
    assert response.status_code == 201, response.text

    details = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert details.status_code == 200
    body = details.json()
    derived = body["derived_gravity"]
    assert derived is not None, body
    assert len(body["measurements"]) == 1, body["measurements"]
    assert derived["source_measurement_ids"], derived
    assert derived["final_gravity_sg"] is not None, derived
    assert Decimal(derived["final_gravity_sg"]) == Decimal("1.012")
    expected_abv = try_abv_percent(og, Decimal("1.012"))
    assert expected_abv != CALCULATION_UNDEFINED
    assert derived["abv_percent"] is not None, derived
    assert Decimal(derived["abv_percent"]) == expected_abv
    expected_att = try_apparent_attenuation_ratio(og, Decimal("1.012"))
    assert expected_att != CALCULATION_UNDEFINED
    # Persisted Numeric(8,6) rounds; compare at storage precision.
    assert Decimal(derived["apparent_attenuation_ratio"]) == expected_att.quantize(
        Decimal("0.000001")
    )
    assert derived["calculation_version"] == "phase4-stable-gravity-v1"

    with SessionLocal() as db:
        snap = db.scalar(
            select(FermentationDerivedGravitySnapshot)
            .where(
                FermentationDerivedGravitySnapshot.fermentation_session_id
                == uuid.UUID(session_id)
            )
            .order_by(FermentationDerivedGravitySnapshot.evaluated_at.desc())
        )
        assert snap is not None
        assert snap.abv_percent == expected_abv


def test_abv_undefined_when_og_unknown(completed_brew_without_og):
    """UNKNOWN OG must not fabricate ABV."""
    client = completed_brew_without_og["client"]
    brew_id = completed_brew_without_og["session_id"]
    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["og_consumption"]["og_availability"] == "UNKNOWN"
    session_id = body["id"]
    active = next(
        s for s in body["stages"] if s["canonical_stage_type"] == "ACTIVE_FERMENTATION"
    )
    started_ctx = {
        "client": client,
        "fermentation_session_id": session_id,
        "active_stage_id": active["id"],
    }
    measured = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(started_ctx, value="1.020"),
    )
    assert measured.status_code == 201, measured.text
    details = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    derived = details["derived_gravity"]
    assert Decimal(derived["final_gravity_sg"]) == Decimal("1.020")
    assert derived["abv_percent"] is None
    assert derived["apparent_attenuation_ratio"] is None


def test_abv_recomputes_after_gravity_correction(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    og = Decimal("1.052")

    created = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(started_fermentation, value="1.020"),
    )
    assert created.status_code == 201
    measurement_id = created.json()["id"]
    before = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["derived_gravity"]
    assert Decimal(before["abv_percent"]) == try_abv_percent(og, Decimal("1.020"))

    correction = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{measurement_id}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": measurement_id,
            "reason": "Corrected FG for ABV recalculation after misread",
            "value": "1.010",
            "unit": "SG",
            "method": "HYDROMETER",
        },
    )
    assert correction.status_code == 201, correction.text
    after = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["derived_gravity"]
    assert Decimal(after["abv_percent"]) == try_abv_percent(og, Decimal("1.010"))
    assert Decimal(after["abv_percent"]) != Decimal(before["abv_percent"])


def test_abv_recomputes_after_og_reconcile(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_id = completed_brew_with_pitch["session_id"]
    og_id = completed_brew_with_pitch["og_measurement_id"]

    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201
    session_id = started.json()["id"]
    active = next(
        s
        for s in started.json()["stages"]
        if s["canonical_stage_type"] == "ACTIVE_FERMENTATION"
    )
    started_ctx = {
        "client": client,
        "fermentation_session_id": session_id,
        "active_stage_id": active["id"],
    }
    client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(started_ctx, value="1.012"),
    )
    before = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert Decimal(before["derived_gravity"]["abv_percent"]) == try_abv_percent(
        Decimal("1.052"), Decimal("1.012")
    )
    revision = before["revision"]

    correction = client.post(
        f"/api/v1/brew-sessions/measurements/{og_id}/corrections",
        json=_measurement("ORIGINAL_GRAVITY", "1.060", "SG"),
    )
    assert correction.status_code == 201
    corrected_id = correction.json()["id"]
    # Phase 3 correction alone must not change Phase 4 ABV pin inputs
    mid = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["derived_gravity"]
    assert mid["abv_percent"] == before["derived_gravity"]["abv_percent"]

    reconciled = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/og-consumption",
        json={
            "operation_id": str(uuid.uuid4()),
            "brew_measurement_id": corrected_id,
            "expected_revision": revision,
        },
    )
    assert reconciled.status_code == 200, reconciled.text
    after = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["derived_gravity"]
    assert Decimal(after["abv_percent"]) == try_abv_percent(Decimal("1.060"), Decimal("1.012"))


def test_calc_read_model_forged_session_404(started_fermentation):
    client = started_fermentation["client"]
    response = client.get(f"/api/v1/fermentation-sessions/{uuid.uuid4()}")
    assert response.status_code == 404


def test_calc_read_model_cross_owner_404(started_fermentation, client):
    owner_client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    owner_client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(started_fermentation, value="1.018"),
    )
    assert owner_client.get(f"/api/v1/fermentation-sessions/{session_id}").json()[
        "derived_gravity"
    ]["abv_percent"] is not None

    with SessionLocal() as db:
        db.add(
            User(
                username="other-calc-reader",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "other-calc-reader", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert client.get(f"/api/v1/fermentation-sessions/{session_id}").status_code == 404


def test_recovery_reread_abv_from_persistence(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json=_gravity_payload(started_fermentation, value="1.015"),
    )
    first = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["derived_gravity"]
    assert first["abv_percent"] is not None
    second = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["derived_gravity"]
    assert second["abv_percent"] == first["abv_percent"]
    assert second["apparent_attenuation_ratio"] == first["apparent_attenuation_ratio"]
    assert second["source_measurement_ids"] == first["source_measurement_ids"]
