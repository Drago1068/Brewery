"""Slice 9 — PLAN_EQUIPMENT_CLOSURE (P4-FR-011 / AC-028,049,064 / ADV-029,039)."""
# ruff: noqa: F811 - test parameters intentionally shadow the fixture import

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from phase4_fixtures import completed_brew_with_pitch, started_fermentation  # noqa: F401
from sqlalchemy import select
from test_phase2_core import equipment_payload

from brewing_api.application.auth import password_hash
from brewing_api.application.phase4.plan import (
    logical_plan_hash,
    materialize_phase4_plan,
    phase4_requirement_template_id,
)
from brewing_api.domain.equipment.models import EquipmentProfile
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationPlanSnapshot,
    FermentationReminder,
    FermentationSession,
)
from brewing_api.domain.identity.models import User
from brewing_api.domain.recipes.models import RecipeProcessStep, RecipeVersion
from brewing_api.main import app
from brewing_api.platform.database import SessionLocal


def _brew_recipe_version_id(brew_session_id: str) -> uuid.UUID:
    from brewing_api.domain.brew_sessions.models import BrewSession

    with SessionLocal() as db:
        brew = db.get(BrewSession, uuid.UUID(brew_session_id))
        assert brew is not None
        return brew.recipe_version_id


def _insert_foundation_steps(
    recipe_version_id: uuid.UUID,
    *,
    count: int = 1,
    details: dict | None = None,
    temperature_c: str | None = "18.0",
) -> None:
    with SessionLocal() as db:
        for index in range(count):
            db.add(
                RecipeProcessStep(
                    recipe_version_id=recipe_version_id,
                    step_type="FERMENTATION_FOUNDATION",
                    sequence=index + 1,
                    name=f"Fermentation foundation {index + 1}",
                    duration_minutes=10080,
                    temperature_c=None if temperature_c is None else Decimal(temperature_c),
                    details=details or {},
                )
            )
        db.commit()


def test_ac028_duplicate_fermentation_foundation_rejects_start(completed_brew_with_pitch):
    """P4-AC-028: duplicate FERMENTATION_FOUNDATION → 422, no session."""
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    recipe_version_id = _brew_recipe_version_id(brew_session_id)
    _insert_foundation_steps(recipe_version_id, count=2)

    with SessionLocal() as db:
        before_count = len(
            list(
                db.scalars(
                    select(FermentationSession).where(
                        FermentationSession.brew_session_id == uuid.UUID(brew_session_id)
                    )
                ).all()
            )
        )

    response = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "PLAN_MATERIALIZATION_FAILED"
    assert any(
        failure.get("reason") == "DUPLICATE_FERMENTATION_FOUNDATION"
        for failure in body.get("failures", [])
    )
    with SessionLocal() as db:
        after_count = len(
            list(
                db.scalars(
                    select(FermentationSession).where(
                        FermentationSession.brew_session_id == uuid.UUID(brew_session_id)
                    )
                ).all()
            )
        )
    assert after_count == before_count


def test_ac049_adv029_equipment_snapshot_immutable_after_live_edit(completed_brew_with_pitch):
    """P4-AC-049 / P4-ADV-029: live equipment edit must not rewrite historical snapshot."""
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    equipment = client.post("/api/v1/equipment-profiles", json=equipment_payload("Ferm Tank A"))
    assert equipment.status_code == 201, equipment.text
    equipment_id = equipment.json()["id"]

    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={
            "operation_id": str(uuid.uuid4()),
            "equipment_profile_id": equipment_id,
        },
    )
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    original_snapshot = started.json()["equipment_snapshot"]
    assert original_snapshot is not None
    assert original_snapshot["source_equipment_profile_id"] == equipment_id
    assert original_snapshot["name"] == "Ferm Tank A"
    assert Decimal(original_snapshot["fermenter_loss_liters"]) == Decimal("1")
    assert original_snapshot["source_deleted"] is False
    assert started.json()["fermenter_identity"] == "SPECIFIED"

    with SessionLocal() as db:
        profile = db.get(EquipmentProfile, uuid.UUID(equipment_id))
        assert profile is not None
        profile.name = "Ferm Tank A EDITED"
        profile.fermenter_loss_liters = Decimal("9.999")
        db.commit()

    reread = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert reread.status_code == 200, reread.text
    assert reread.json()["equipment_snapshot"] == original_snapshot
    assert reread.json()["equipment_snapshot"]["name"] == "Ferm Tank A"
    assert Decimal(reread.json()["equipment_snapshot"]["fermenter_loss_liters"]) == Decimal("1")


def test_adv039_schedule_included_in_plan_hash(completed_brew_with_pitch):
    """P4-ADV-039: details.schedule is applied into snapshot and logical hash."""
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    recipe_version_id = _brew_recipe_version_id(brew_session_id)
    schedule = [
        {"effective_offset_minutes": 120, "target_temp_c": "18.0"},
        {"effective_offset_minutes": 0, "target_temp_c": "20.0"},
    ]
    _insert_foundation_steps(
        recipe_version_id,
        count=1,
        details={"schedule": schedule},
        temperature_c="20.0",
    )

    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert started.status_code == 201, started.text
    payload = started.json()["plan_snapshot"]["payload"]
    assert payload["schedule"] == [
        {"effective_offset_minutes": 0, "target_temp_c": "20.0"},
        {"effective_offset_minutes": 120, "target_temp_c": "18.0"},
    ]
    assert (
        started.json()["logical_plan_hash"] == started.json()["plan_snapshot"]["logical_plan_hash"]
    )

    with SessionLocal() as db:
        version = db.get(RecipeVersion, recipe_version_id)
        assert version is not None
        plan = materialize_phase4_plan(db, version)
        assert plan.schedule is not None
        assert logical_plan_hash(plan) == started.json()["logical_plan_hash"]
        from dataclasses import replace

        without_schedule = replace(plan, schedule=None)
        assert logical_plan_hash(without_schedule) != started.json()["logical_plan_hash"]


def test_ac064_abort_restart_same_template_ids_and_hash_distinct_rows(completed_brew_with_pitch):
    """P4-AC-064: abort then restart → same templates/hash; distinct requirement row IDs."""
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    recipe_version_id = _brew_recipe_version_id(brew_session_id)
    _insert_foundation_steps(
        recipe_version_id,
        count=1,
        details={
            "schedule": [
                {"effective_offset_minutes": 0, "target_temp_c": "19.0"},
                {"effective_offset_minutes": 2880, "target_temp_c": "17.0"},
            ]
        },
        temperature_c="19.0",
    )

    first = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]
    first_hash = first.json()["logical_plan_hash"]
    first_schedule = first.json()["plan_snapshot"]["payload"]["schedule"]
    first_templates = {
        row["requirement_template_id"]
        for row in first.json()["plan_snapshot"]["payload"]["requirement_templates"]
    }
    expected_gravity = str(
        phase4_requirement_template_id(
            recipe_version_id, "FERMENTATION_GRAVITY_STABILITY", "default"
        )
    )
    assert expected_gravity in first_templates

    with SessionLocal() as db:
        first_reminder = db.scalar(
            select(FermentationReminder).where(
                FermentationReminder.fermentation_session_id == uuid.UUID(first_id),
                FermentationReminder.requirement_class == "FERMENTATION_GRAVITY_STABILITY",
            )
        )
        assert first_reminder is not None
        first_row_id = first_reminder.id
        first_template_id = first_reminder.requirement_template_id

    aborted = client.post(
        f"/api/v1/fermentation-sessions/{first_id}/commands/abort",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": first.json()["revision"],
            "reason": "Aborting to restart fermentation with same plan schedule",
        },
    )
    assert aborted.status_code == 200, aborted.text

    second = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": str(uuid.uuid4())},
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]
    assert second_id != first_id
    assert second.json()["logical_plan_hash"] == first_hash
    assert second.json()["plan_snapshot"]["payload"]["schedule"] == first_schedule
    second_templates = {
        row["requirement_template_id"]
        for row in second.json()["plan_snapshot"]["payload"]["requirement_templates"]
    }
    assert second_templates == first_templates

    with SessionLocal() as db:
        second_reminder = db.scalar(
            select(FermentationReminder).where(
                FermentationReminder.fermentation_session_id == uuid.UUID(second_id),
                FermentationReminder.requirement_class == "FERMENTATION_GRAVITY_STABILITY",
            )
        )
        assert second_reminder is not None
        assert second_reminder.requirement_template_id == first_template_id
        assert second_reminder.id != first_row_id


def test_equipment_reference_integrity_cross_owner_and_missing(completed_brew_with_pitch):
    owner = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    equipment = owner.post("/api/v1/equipment-profiles", json=equipment_payload("Owner Tank"))
    assert equipment.status_code == 201, equipment.text
    equipment_id = equipment.json()["id"]

    missing = owner.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={
            "operation_id": str(uuid.uuid4()),
            "equipment_profile_id": str(uuid.uuid4()),
        },
    )
    assert missing.status_code == 404
    assert missing.json().get("detail") == "Equipment profile not found"

    with SessionLocal() as db:
        db.add(
            User(
                username="slice9-other",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()

    # Same TestClient cookie jar: switch identity then assert nondisclosure of owner brew.
    login = owner.post(
        "/api/v1/auth/login",
        json={"username": "slice9-other", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    owner.headers["X-CSRF-Token"] = login.json()["csrf_token"]

    foreign_start = owner.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={
            "operation_id": str(uuid.uuid4()),
            "equipment_profile_id": equipment_id,
        },
    )
    assert foreign_start.status_code == 404


def test_no_equipment_is_lawful_unspecified(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    body = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert body["equipment_snapshot"] is None
    assert body["source_equipment_profile_id"] is None
    assert body["fermenter_identity"] == "UNSPECIFIED"


def test_start_idempotency_includes_equipment_key(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    equipment = client.post("/api/v1/equipment-profiles", json=equipment_payload("Idem Tank"))
    assert equipment.status_code == 201, equipment.text
    equipment_id = equipment.json()["id"]
    op = str(uuid.uuid4())
    payload = {"operation_id": op, "equipment_profile_id": equipment_id}

    first = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json=payload,
    )
    assert first.status_code == 201, first.text
    replay = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json=payload,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == first.json()["id"]

    conflict = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={"operation_id": op, "equipment_profile_id": str(uuid.uuid4())},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_journal_records_equipment_association(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    equipment = client.post("/api/v1/equipment-profiles", json=equipment_payload("Journal Tank"))
    assert equipment.status_code == 201, equipment.text
    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={
            "operation_id": str(uuid.uuid4()),
            "equipment_profile_id": equipment.json()["id"],
        },
    )
    assert started.status_code == 201, started.text
    session_id = uuid.UUID(started.json()["id"])
    with SessionLocal() as db:
        event = db.scalar(
            select(FermentationJournalEvent).where(
                FermentationJournalEvent.fermentation_session_id == session_id,
                FermentationJournalEvent.event_type == "FERMENTATION_SESSION_STARTED",
            )
        )
        assert event is not None
        assert event.event_data["equipment_snapshotted"] is True
        assert event.event_data["source_equipment_profile_id"] == equipment.json()["id"]


def test_recovery_reread_plan_and_equipment_from_persistence(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    recipe_version_id = _brew_recipe_version_id(brew_session_id)
    _insert_foundation_steps(
        recipe_version_id,
        details={"schedule": [{"effective_offset_minutes": 0, "target_temp_c": "18.5"}]},
    )
    equipment = client.post("/api/v1/equipment-profiles", json=equipment_payload("Recover Tank"))
    assert equipment.status_code == 201, equipment.text
    started = client.post(
        f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
        json={
            "operation_id": str(uuid.uuid4()),
            "equipment_profile_id": equipment.json()["id"],
        },
    )
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    expected_hash = started.json()["logical_plan_hash"]
    expected_equip = started.json()["equipment_snapshot"]

    with TestClient(app) as fresh:
        fresh.headers["Origin"] = "http://testserver"
        login = fresh.post(
            "/api/v1/auth/login",
            json={"username": "brewer", "password": "test-password-not-a-secret"},
        )
        assert login.status_code == 200
        fresh.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        reread = fresh.get(f"/api/v1/fermentation-sessions/{session_id}")
        assert reread.status_code == 200, reread.text
        assert reread.json()["logical_plan_hash"] == expected_hash
        assert reread.json()["equipment_snapshot"] == expected_equip
        assert reread.json()["plan_snapshot"]["payload"]["schedule"] == [
            {"effective_offset_minutes": 0, "target_temp_c": "18.5"}
        ]


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("TEST_USE_POSTGRES") != "1",
    reason="Slice 9 concurrency requires PostgreSQL",
)
def test_concurrent_start_one_session_with_equipment(completed_brew_with_pitch):
    client = completed_brew_with_pitch["client"]
    brew_session_id = completed_brew_with_pitch["session_id"]
    equipment = client.post("/api/v1/equipment-profiles", json=equipment_payload("Race Tank"))
    assert equipment.status_code == 201, equipment.text
    equipment_id = equipment.json()["id"]
    barrier = threading.Barrier(2)
    results: list[tuple[int, str | None]] = []

    def worker(op_suffix: str) -> None:
        barrier.wait()
        response = client.post(
            f"/api/v1/fermentation-sessions/brew-sessions/{brew_session_id}/start",
            json={
                "operation_id": f"slice9-race-{op_suffix}-{uuid.uuid4()}",
                "equipment_profile_id": equipment_id,
            },
        )
        body = response.json() if response.content else {}
        results.append((response.status_code, body.get("id")))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, "a"), pool.submit(worker, "b")]
        for future in futures:
            future.result()

    successes = [item for item in results if item[0] == 201]
    conflicts = [item for item in results if item[0] == 409]
    assert len(successes) == 1
    assert len(conflicts) == 1
    with SessionLocal() as db:
        sessions = list(
            db.scalars(
                select(FermentationSession).where(
                    FermentationSession.brew_session_id == uuid.UUID(brew_session_id),
                    FermentationSession.status != "ABORTED",
                )
            ).all()
        )
        assert len(sessions) == 1
        assert sessions[0].source_equipment_profile_id == uuid.UUID(equipment_id)
        assert sessions[0].equipment_snapshot is not None
        snapshots = list(
            db.scalars(
                select(FermentationPlanSnapshot).where(
                    FermentationPlanSnapshot.fermentation_session_id == sessions[0].id
                )
            ).all()
        )
        assert len(snapshots) == 1
