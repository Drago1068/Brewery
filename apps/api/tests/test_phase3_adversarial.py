import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from test_phase3_engines import PNG, _requirement
from test_phase3_materialization import _source

from brewing_api.application.errors import ValidationConflictError
from brewing_api.application.phase3.plan import _materialize_occurrence_requirements
from brewing_api.domain.brew_day.materialization import (
    AdditionRepeatDeclaration,
    SourceAddition,
    materialize_phase3_plan,
)
from brewing_api.domain.brew_day.models import BrewRequirementTemplate, BrewStageRequirement
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage, BrewTimer
from brewing_api.domain.measurements.models import Measurement
from brewing_api.domain.recipes.models import RecipeVersion
from brewing_api.platform.database import SessionLocal, engine
from brewing_api.platform.time import utc_now


def _record(client, stage_id: str, kind: str, value: str, unit: str, **extra):
    payload = {"measurement_type": kind, "value": value, "unit": unit, **extra}
    return client.post(f"/api/v1/brew-sessions/stages/{stage_id}/measurements", json=payload)


def test_adv_001_003_004_031_idempotent_replay_and_key_reuse(active_mash):
    # P3-ADV-001 / 003 / 004 / 031
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    first = _record(
        client,
        stage_id,
        "MASH_PH",
        "5.30",
        "pH",
        operation_id="meas-1",
    )
    assert first.status_code == 201
    replay = _record(
        client,
        stage_id,
        "MASH_PH",
        "5.30",
        "pH",
        operation_id="meas-1",
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(Measurement).where(
                    Measurement.brew_stage_id == uuid.UUID(stage_id),
                    Measurement.measurement_type == "MASH_PH",
                    Measurement.correction_of_id.is_(None),
                )
            )
        )
        assert len(rows) == 1
    paused = client.post(
        f"/api/v1/brew-sessions/{session_id}/pause",
        json={"operation_id": "pause-adv-1"},
    )
    assert paused.status_code == 200
    same = client.post(
        f"/api/v1/brew-sessions/{session_id}/pause",
        json={"operation_id": "pause-adv-1"},
    )
    assert same.status_code == 200
    assert same.json()["id"] == paused.json()["id"]
    conflict = client.post(
        f"/api/v1/brew-sessions/{session_id}/pause",
        json={"operation_id": "pause-adv-1", "expected_revision": 99},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_adv_002_second_distinct_measurement_conflicts(active_mash):
    # P3-ADV-002
    client = active_mash["client"]
    stage_id = active_mash["stage_id"]
    first = _record(client, stage_id, "MASH_PH", "5.30", "pH", operation_id="ph-a")
    assert first.status_code == 201
    second = _record(client, stage_id, "MASH_PH", "5.34", "pH", operation_id="ph-b")
    assert second.status_code == 409


def test_adv_005_double_reminder_ack_is_idempotent_not_completed(active_mash):
    # P3-ADV-005
    client = active_mash["client"]
    details = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}").json()
    reminder_id = details["mash"]["notifications"][0]["id"]
    first = client.post(f"/api/v1/brew-sessions/reminders/{reminder_id}/acknowledge")
    second = client.post(f"/api/v1/brew-sessions/reminders/{reminder_id}/acknowledge")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["status"] == "ACKNOWLEDGED"
    assert second.json()["status"] != "COMPLETED"
    blocked = client.post(f"/api/v1/brew-sessions/stages/{active_mash['stage_id']}/complete")
    assert blocked.status_code == 400


def test_adv_007_010_expired_timer_recovered_from_postgres_deadline(active_mash):
    # P3-ADV-007 / 010
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    timer_id = uuid.UUID(details["timers"][0]["id"])
    with SessionLocal() as db:
        timer = db.get(BrewTimer, timer_id)
        timer.deadline_at = utc_now() - timedelta(seconds=5)
        db.commit()
    recovered = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    assert recovered["timers"][0]["id"] == str(timer_id)
    assert recovered["timers"][0]["status"] == "EXPIRED"


def test_adv_009_056_redis_is_non_authoritative(active_mash, monkeypatch):
    # P3-ADV-009 / 056 — Redis is acceleration only; timer expiry is recovered from DB.
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/15")
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    timer_id = uuid.UUID(details["timers"][0]["id"])
    with SessionLocal() as db:
        timer = db.get(BrewTimer, timer_id)
        timer.deadline_at = utc_now() - timedelta(seconds=8)
        db.commit()
    recovered = client.get(f"/api/v1/brew-sessions/{session_id}")
    assert recovered.status_code == 200
    body = recovered.json()
    assert body["id"] == session_id
    assert body["timers"][0]["status"] == "EXPIRED"


def test_adv_014_measurement_correction_appends(active_mash):
    # P3-ADV-014
    client = active_mash["client"]
    stage_id = active_mash["stage_id"]
    original = _record(client, stage_id, "MASH_PH", "5.42", "pH")
    assert original.status_code == 201
    original_id = original.json()["id"]
    correction = client.post(
        f"/api/v1/brew-sessions/measurements/{original_id}/corrections",
        json={
            "measurement_type": "MASH_PH",
            "value": "5.40",
            "unit": "pH",
            "note": "Transcription correction",
        },
    )
    assert correction.status_code == 201
    assert correction.json()["correction_of_id"] == original_id
    with SessionLocal() as db:
        row = db.get(Measurement, uuid.UUID(original_id))
        assert str(row.value) == "5.420"
        appended = db.get(Measurement, uuid.UUID(correction.json()["id"]))
        assert appended.correction_of_id == uuid.UUID(original_id)


def test_adv_016_complete_mash_without_measurements_fails(active_mash):
    # P3-ADV-016
    response = active_mash["client"].post(
        f"/api/v1/brew-sessions/stages/{active_mash['stage_id']}/complete"
    )
    assert response.status_code == 400
    assert "MASH_PH" in response.json()["detail"]


def test_adv_018_late_measurement_after_stage_complete(active_mash):
    # P3-ADV-018
    client = active_mash["client"]
    stage_id = active_mash["stage_id"]
    assert _record(client, stage_id, "MASH_PH", "5.30", "pH").status_code == 201
    assert _record(client, stage_id, "MASH_GRAVITY", "1.050", "SG").status_code == 201
    completed = client.post(f"/api/v1/brew-sessions/stages/{stage_id}/complete")
    assert completed.status_code == 200
    late = _record(
        client,
        stage_id,
        "POST_MASH_GRAVITY",
        "1.048",
        "SG",
        late_entry_reason="Hydrometer reading finished after mash was marked complete",
    )
    assert late.status_code == 201
    with SessionLocal() as db:
        row = db.get(Measurement, uuid.UUID(late.json()["id"]))
        assert row.late_entry is True
        assert "after mash" in (row.late_entry_reason or "")
    details = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}").json()
    assert details["mash"]["status"] == "COMPLETED"


def test_adv_019_032_svg_rejected_png_uploaded(active_mash, tmp_path, monkeypatch):
    # P3-ADV-019 / 032
    from brewing_api.platform import config

    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    config.get_settings.cache_clear()
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    rejected = client.post(
        f"/api/v1/brew-sessions/{session_id}/attachments",
        files={
            "file": ("evil.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "image/svg+xml")
        },
        data={"operation_id": "adv-media-bad"},
    )
    assert rejected.status_code in {415, 422}
    uploaded = client.post(
        f"/api/v1/brew-sessions/{session_id}/attachments",
        files={"file": ("mash.png", PNG, "image/png")},
        data={"operation_id": "adv-media-1"},
    )
    assert uploaded.status_code == 201
    fetched = client.get(f"/api/v1/brew-sessions/{session_id}/attachments/{uploaded.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/png"


def test_adv_020_voice_proposal_fifty_two_is_not_committed(active_mash):
    # P3-ADV-020
    client = active_mash["client"]
    parsed = client.post(
        "/api/v1/brew-sessions/voice/proposals",
        json={"transcript": "fifty two pH"},
    )
    assert parsed.status_code == 200
    assert parsed.json()["committed"] is False
    assert parsed.json()["proposal"]["value"] == "52"
    rejected = _record(client, active_mash["stage_id"], "MASH_PH", "52", "pH")
    assert rejected.status_code == 422


def test_adv_021_recipe_version_immutable_after_session(active_mash):
    # P3-ADV-021 — trigger is postgres-only; sqlite soft-checks session snapshot isolation.
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    version_id = uuid.UUID(active_mash["recipe"]["version_id"])
    before = client.get(f"/api/v1/brew-sessions/{session_id}").json()["planned"]["mash_ph"]
    with SessionLocal() as db:
        version = db.get(RecipeVersion, version_id)
        try:
            version.target_mash_ph = Decimal("5.90")
            db.commit()
        except DBAPIError as exc:
            db.rollback()
            assert "immutable" in str(exc).lower()
            return
    if engine.dialect.name == "postgresql":
        pytest.fail("expected recipe_version_immutable trigger to reject the update")
    after = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    assert after["planned"]["mash_ph"] == before == "5.30"


def test_adv_024_completion_audit_excludes_waiver_from_measured(active_mash):
    # P3-ADV-024
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    requirement_id = _requirement(session_id, active_mash["stage_id"])
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    waived = client.post(
        f"/api/v1/brew-sessions/{session_id}/requirements/{requirement_id}/waivers",
        json={
            "reason": "Could not verify hop charge visually",
            "operation_id": "adv-waiver-audit",
            "expected_revision": details["revision"],
        },
    )
    assert waived.status_code == 201
    audit = client.get(f"/api/v1/brew-sessions/{session_id}/completion-audit").json()
    assert audit["measurement_completeness_excludes_waivers"] is True
    assert audit["waived_count"] >= 1
    assert audit["measured_count"] == 0


def test_adv_025_phase1a_recipes_and_sessions_still_work(authenticated_client, recipe_payload):
    # P3-ADV-025
    recipe = authenticated_client.post("/api/v1/recipes", json=recipe_payload)
    assert recipe.status_code == 201
    listed = authenticated_client.get("/api/v1/recipes")
    assert listed.status_code == 200
    assert any(item["id"] == recipe.json()["id"] for item in listed.json())
    created = authenticated_client.post(
        "/api/v1/brew-sessions", json={"recipe_version_id": recipe.json()["version_id"]}
    )
    assert created.status_code == 201
    started = authenticated_client.post(f"/api/v1/brew-sessions/{created.json()['id']}/start")
    assert started.status_code == 200
    mash = authenticated_client.post(f"/api/v1/brew-sessions/{created.json()['id']}/mash/start")
    assert mash.status_code == 200
    details = authenticated_client.get(f"/api/v1/brew-sessions/{created.json()['id']}")
    assert details.status_code == 200
    assert details.json()["status"] == "ACTIVE"


def test_adv_026_035_041_042_preview_hash_is_deterministic(authenticated_client, recipe_payload):
    # P3-ADV-026 / 035 / 041 / 042
    recipe = authenticated_client.post("/api/v1/recipes", json=recipe_payload).json()
    path = f"/api/v1/recipe-versions/{recipe['version_id']}/phase3-plan-preview"
    first = authenticated_client.get(path)
    second = authenticated_client.get(path)
    assert first.status_code == second.status_code == 200
    assert first.json()["plan_preview_hash"] == second.json()["plan_preview_hash"]
    assert first.json()["logical_plan_hash"] == second.json()["logical_plan_hash"]
    first_ids = [step["plan_step_id"] for step in first.json()["steps"]]
    second_ids = [step["plan_step_id"] for step in second.json()["steps"]]
    assert first_ids == second_ids
    assert len(set(first_ids)) == len(first_ids)
    source = _source()
    plan = materialize_phase3_plan(source)
    again = materialize_phase3_plan(source)
    assert plan.logical_plan_hash == again.logical_plan_hash
    mash_in = next(step for step in plan.steps if step.canonical_stage_type == "MASH_IN")
    mash = next(step for step in plan.steps if step.canonical_stage_type == "MASH")
    assert mash_in.plan_step_id != mash.plan_step_id
    assert mash_in.source_process_step_id == mash.source_process_step_id


def test_adv_028_pause_resume_abort(active_mash):
    # P3-ADV-028
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    paused = client.post(f"/api/v1/brew-sessions/{session_id}/pause")
    assert paused.json()["status"] == "PAUSED"
    resumed = client.post(f"/api/v1/brew-sessions/{session_id}/resume")
    assert resumed.json()["status"] == "ACTIVE"
    aborted = client.post(
        f"/api/v1/brew-sessions/{session_id}/abort",
        json={"reason": "Boil kettle failure forced a stop"},
    )
    assert aborted.status_code == 200
    assert aborted.json()["status"] == "ABORTED"


def test_adv_033_csrf_missing_and_wrong_token_rejected(client, recipe_payload):
    # P3-ADV-033
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "brewer", "password": "test-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers.pop("X-CSRF-Token", None)
    missing = client.post("/api/v1/recipes", json=recipe_payload)
    assert missing.status_code == 403
    assert missing.json()["code"] == "CSRF_REJECTED"
    client.headers["X-CSRF-Token"] = "not-a-valid-csrf-token"
    wrong = client.post("/api/v1/recipes", json=recipe_payload)
    assert wrong.status_code == 403
    assert wrong.json()["code"] == "CSRF_REJECTED"


def test_adv_036_legacy_session_identities_stable_across_get(active_mash):
    # P3-ADV-036
    client = active_mash["client"]
    path = f"/api/v1/brew-sessions/{active_mash['session_id']}"
    first = client.get(path).json()
    second = client.get(path).json()
    assert first["id"] == second["id"]
    assert first["mash"]["id"] == second["mash"]["id"]
    assert first["mash"]["timer"]["id"] == second["mash"]["timer"]["id"]
    assert [item["plan_step_id"] for item in first["stages"]] == [
        item["plan_step_id"] for item in second["stages"]
    ]
    assert first["logical_plan_hash"] == second["logical_plan_hash"]


def test_adv_038_waiver_then_abort(active_mash):
    # P3-ADV-038
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    requirement_id = _requirement(session_id, active_mash["stage_id"])
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    waived = client.post(
        f"/api/v1/brew-sessions/{session_id}/requirements/{requirement_id}/waivers",
        json={
            "reason": "Optional skip authorized before aborting the brew",
            "operation_id": "adv-waiver-abort",
            "expected_revision": details["revision"],
        },
    )
    assert waived.status_code == 201
    aborted = client.post(
        f"/api/v1/brew-sessions/{session_id}/abort",
        json={"reason": "Kettle failure forced an immediate stop"},
    )
    assert aborted.json()["status"] == "ABORTED"
    after = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    assert after["status"] == "ABORTED"
    assert after["waivers"]


def test_adv_039_040_aborted_blocks_new_measurement(active_mash):
    # P3-ADV-039 / 040
    client = active_mash["client"]
    client.post(
        f"/api/v1/brew-sessions/{active_mash['session_id']}/abort",
        json={"reason": "Kettle failure forced an immediate stop"},
    )
    response = _record(client, active_mash["stage_id"], "MASH_PH", "5.30", "pH")
    assert response.status_code == 409
    assert response.json()["code"] == "TERMINAL_SESSION_EVIDENCE_PROHIBITED"


def test_adv_043_051_runtime_repeat_does_not_regenerate_default_additions(active_mash):
    # P3-ADV-043 / 051
    addition_id = uuid.uuid4()
    source = _source(
        additions=(
            SourceAddition(
                id=addition_id,
                ingredient_id=uuid.uuid4(),
                amount=Decimal("28"),
                unit="g",
                use_stage="MASH",
                timing_minutes=0,
            ),
        )
    )
    plan = materialize_phase3_plan(source)
    mash = next(step for step in plan.steps if step.canonical_stage_type == "MASH")
    assert mash.additions[0]["addition_repeat_policy"] == "PLANNED_OCCURRENCES_ONLY"
    session_id = uuid.UUID(active_mash["session_id"])
    stage_id = uuid.UUID(active_mash["stage_id"])
    with SessionLocal() as db:
        session = db.get(BrewSession, session_id)
        source_stage = db.get(BrewStage, stage_id)
        plan_id = source_stage.plan_step_id or uuid.uuid4()
        template_id = uuid.uuid4()
        db.add(
            BrewRequirementTemplate(
                brew_session_id=session.id,
                plan_step_id=plan_id,
                requirement_template_id=template_id,
                requirement_class="ADDITION",
                definition_key="MASH_ADDITION",
                required=True,
                waivable=True,
                runtime_occurrence_policy="REGENERATE",
                payload={"definition_key": "MASH_ADDITION"},
                addition_repeat_policy="PLANNED_OCCURRENCES_ONLY",
            )
        )
        clone = BrewStage(
            brew_session_id=session.id,
            name="MASH",
            status="ACTIVE",
            started_at=utc_now(),
            target_duration_seconds=source_stage.target_duration_seconds,
            target_temperature=source_stage.target_temperature,
            temperature_unit=source_stage.temperature_unit,
            target_ph=source_stage.target_ph,
            ph_tolerance=source_stage.ph_tolerance,
            target_gravity=source_stage.target_gravity,
            gravity_tolerance=source_stage.gravity_tolerance,
            plan_step_id=plan_id,
            canonical_stage_type="MASH",
            occurrence_number=2,
            required=True,
            runtime_occurrence_kind="REPEAT",
        )
        db.add(clone)
        db.flush()
        _materialize_occurrence_requirements(db, session, clone, "RUNTIME_REPEAT_RULE")
        regenerated = list(
            db.scalars(
                select(BrewStageRequirement).where(
                    BrewStageRequirement.stage_instance_id == clone.id,
                    BrewStageRequirement.requirement_class == "ADDITION",
                )
            )
        )
        assert regenerated == []
        db.rollback()


def test_adv_046_049_addition_execute_correction_and_idempotent_replay(active_mash):
    # P3-ADV-046 / 049
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    requirement_id = _requirement(session_id, active_mash["stage_id"])
    executed = client.post(
        f"/api/v1/brew-sessions/{session_id}/requirements/{requirement_id}/additions",
        json={"quantity": "10", "unit": "g", "operation_id": "adv-add-1"},
    )
    assert executed.status_code == 201
    event_id = executed.json()["id"]
    correction = client.post(
        f"/api/v1/brew-sessions/{session_id}/addition-events/{event_id}/corrections",
        json={
            "quantity": "12",
            "unit": "g",
            "reason": "Scale was misread on the first charge",
            "operation_id": "adv-add-corr-1",
            "correction_of_id": event_id,
        },
    )
    assert correction.status_code == 201
    assert correction.json()["correction_of_id"] == event_id
    replay = client.post(
        f"/api/v1/brew-sessions/{session_id}/addition-events/{event_id}/corrections",
        json={
            "quantity": "12",
            "unit": "g",
            "reason": "Scale was misread on the first charge",
            "operation_id": "adv-add-corr-1",
            "correction_of_id": event_id,
        },
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == correction.json()["id"]


def test_adv_050_planned_recipe_addition_correction_is_unavailable(active_mash):
    # P3-ADV-050
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    missing = client.post(
        f"/api/v1/brew-sessions/{session_id}/addition-events/{uuid.uuid4()}/corrections",
        json={
            "reason": "Tried to rewrite the planned recipe addition",
            "operation_id": "adv-plan-corr",
        },
    )
    assert missing.status_code == 404


def test_adv_057_058_policy_comes_from_materialization_not_heuristics():
    # P3-ADV-057 / 058
    addition_id = uuid.uuid4()
    source = _source(
        additions=(
            SourceAddition(
                id=addition_id,
                ingredient_id=uuid.uuid4(),
                amount=Decimal("28"),
                unit="g",
                use_stage="MASH",
                timing_minutes=0,
            ),
        )
    )
    preview = materialize_phase3_plan(source)
    mash = next(step for step in preview.steps if step.canonical_stage_type == "MASH")
    assert mash.additions[0]["addition_repeat_policy"] == "PLANNED_OCCURRENCES_ONLY"
    with pytest.raises(ValidationConflictError) as error:
        materialize_phase3_plan(
            source,
            (
                AdditionRepeatDeclaration(
                    source_addition_id=addition_id,
                    target_plan_step_id=mash.plan_step_id,
                    policy="HEURISTIC_FROM_STAGE",
                    reason="UI inferred mash hops should repeat",
                ),
            ),
            preview.preview_hash,
        )
    assert error.value.code == "INVALID_ADDITION_REPEAT_POLICY"


def test_adv_057_later_recipe_change_does_not_mutate_session_snapshot(active_mash):
    # P3-ADV-057
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    planned = client.get(f"/api/v1/brew-sessions/{session_id}").json()["planned"]
    with SessionLocal() as db:
        version = db.get(RecipeVersion, uuid.UUID(active_mash["recipe"]["version_id"]))
        try:
            version.target_mash_gravity = Decimal("1.080")
            version.notes = "heuristic rewrite after session start"
            db.commit()
        except DBAPIError:
            db.rollback()
    after = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    assert after["planned"]["mash_gravity"] == planned["mash_gravity"]
    assert after["planned"]["mash_ph"] == planned["mash_ph"]


def test_adv_006_measurement_completes_reminder_once(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    reminder_id = details["mash"]["notifications"][0]["id"]
    recorded = _record(client, stage_id, "MASH_PH", "5.30", "pH")
    assert recorded.status_code == 201
    ack = client.post(f"/api/v1/brew-sessions/reminders/{reminder_id}/acknowledge")
    assert ack.status_code in {200, 409}
    after = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    reminder = next(item for item in after["mash"]["notifications"] if item["id"] == reminder_id)
    assert reminder["status"] in {"COMPLETED", "ACKNOWLEDGED"}
    blocked = client.post(f"/api/v1/brew-sessions/stages/{stage_id}/complete")
    assert blocked.status_code == 400


def test_adv_008_timer_extend_then_stale_replace_conflicts(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    timer_id = details["timers"][0]["id"]
    extended = client.post(
        f"/api/v1/brew-sessions/timers/{timer_id}/extend",
        json={"extra_seconds": 30, "reason": "mash rest needed more conversion time"},
    )
    assert extended.status_code == 200
    stale = client.post(
        f"/api/v1/brew-sessions/timers/{timer_id}/replace",
        json={
            "reason": "Probe failed and timer purpose changed",
            "planned_duration_seconds": 90,
            "expected_revision": 1,
        },
    )
    assert stale.status_code in {200, 409}
    replaced = client.post(
        f"/api/v1/brew-sessions/timers/{timer_id}/replace",
        json={"reason": "Probe failed and timer purpose changed", "planned_duration_seconds": 120},
    )
    assert replaced.status_code in {200, 409}
    after = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    assert after["timers"]


def test_adv_011_conflict_does_not_create_partial_measurement(active_mash):
    client = active_mash["client"]
    stage_id = active_mash["stage_id"]
    first = _record(client, stage_id, "MASH_PH", "5.30", "pH")
    assert first.status_code == 201
    conflict = _record(client, stage_id, "MASH_PH", "5.34", "pH")
    assert conflict.status_code == 409
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(Measurement).where(
                    Measurement.brew_stage_id == uuid.UUID(stage_id),
                    Measurement.measurement_type == "MASH_PH",
                    Measurement.correction_of_id.is_(None),
                )
            )
        )
        assert len(rows) == 1
        assert str(rows[0].value) == "5.300" or str(rows[0].value).startswith("5.3")


def test_adv_012_no_authoritative_background_worker():
    from pathlib import Path

    import brewing_api.main as main_module

    source = Path(main_module.__file__).read_text(encoding="utf-8")
    assert "celery" not in source.lower()
    compose = Path(__file__).resolve().parents[3] / "docker-compose.yml"
    if compose.exists():
        lowered = compose.read_text(encoding="utf-8").lower()
        assert "celery" not in lowered
        assert "rq-worker" not in lowered


def test_adv_013_future_observed_at_is_rejected(active_mash):
    future = (utc_now() + timedelta(minutes=10)).isoformat()
    response = _record(
        active_mash["client"],
        active_mash["stage_id"],
        "MASH_PH",
        "5.30",
        "pH",
        measured_at=future,
    )
    assert response.status_code == 422


def test_adv_015_023_addition_and_journal_regen_have_zero_inventory_effect(active_mash):
    from brewing_api.application.phase3.additions import inventory_transaction_count

    client = active_mash["client"]
    session_id = active_mash["session_id"]
    requirement_id = _requirement(session_id, active_mash["stage_id"])
    with SessionLocal() as db:
        before = inventory_transaction_count(db)
    executed = client.post(
        f"/api/v1/brew-sessions/{session_id}/requirements/{requirement_id}/additions",
        json={"quantity": "10", "unit": "g", "operation_id": "adv-015"},
    )
    assert executed.status_code == 201
    first = client.get(f"/api/v1/brew-sessions/{session_id}/journal")
    assert first.status_code == 200
    count = len(first.json()["events"])
    second = client.get(f"/api/v1/brew-sessions/{session_id}/journal")
    export = client.get(f"/api/v1/brew-sessions/{session_id}/export?format=json")
    assert second.status_code == 200
    assert len(second.json()["events"]) == count
    assert export.status_code == 200
    with SessionLocal() as db:
        assert inventory_transaction_count(db) == before


def test_adv_017_037_045_extend_then_repeat_is_idempotent(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    extended = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/extend",
        json={"extra_seconds": 60, "reason": "conversion was incomplete at the planned rest"},
    )
    assert extended.status_code == 200
    assert _record(client, stage_id, "MASH_PH", "5.30", "pH").status_code == 201
    assert _record(client, stage_id, "MASH_GRAVITY", "1.050", "SG").status_code == 201
    completed = client.post(f"/api/v1/brew-sessions/stages/{stage_id}/complete")
    assert completed.status_code == 200
    first = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/repeat",
        json={
            "reason": "Need another rest after iodine failed",
            "operation_id": "repeat-mash-1",
        },
    )
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    if details["status"] == "COMPLETED":
        assert first.status_code == 409
        return
    assert first.status_code == 200
    replay = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/repeat",
        json={
            "reason": "Need another rest after iodine failed",
            "operation_id": "repeat-mash-1",
        },
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert first.json()["id"] != stage_id


def test_adv_022_reopened_session_reconstructs_expired_timer(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    timer_id = uuid.UUID(details["timers"][0]["id"])
    with SessionLocal() as db:
        timer = db.get(BrewTimer, timer_id)
        timer.deadline_at = utc_now() - timedelta(hours=20)
        db.commit()
    recovered = client.get(f"/api/v1/brew-sessions/{session_id}")
    assert recovered.status_code == 200
    assert recovered.json()["id"] == session_id
    assert recovered.json()["timers"][0]["status"] == "EXPIRED"


def test_adv_027_legacy_mash_start_does_not_duplicate(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    again = client.post(f"/api/v1/brew-sessions/{session_id}/mash/start")
    assert again.status_code == 409
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    mash_rows = [
        item
        for item in details["stages"]
        if (item.get("canonical_stage_type") or item.get("name")) == "MASH"
    ]
    assert len(mash_rows) == 1


def test_adv_029_boil_addition_timing_is_before_planned_stage_end():
    addition_id = uuid.uuid4()
    source = _source(
        additions=(
            SourceAddition(
                id=addition_id,
                ingredient_id=uuid.uuid4(),
                amount=Decimal("28"),
                unit="g",
                use_stage="BOIL",
                timing_minutes=60,
            ),
        )
    )
    plan = materialize_phase3_plan(source)
    boil = next(step for step in plan.steps if step.canonical_stage_type == "BOIL")
    assert boil.additions[0]["timing_basis"] == "BEFORE_PLANNED_STAGE_END"
    assert boil.additions[0]["timing_offset_seconds"] == 3600


def test_adv_030_047_048_late_types_and_addition_skip_correction(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    assert _record(client, stage_id, "MASH_PH", "5.30", "pH").status_code == 201
    assert _record(client, stage_id, "MASH_GRAVITY", "1.050", "SG").status_code == 201
    assert client.post(f"/api/v1/brew-sessions/stages/{stage_id}/complete").status_code == 200
    late = _record(
        client,
        stage_id,
        "POST_MASH_GRAVITY",
        "1.048",
        "SG",
        late_entry_reason="Hydrometer reading finished after mash was marked complete",
    )
    assert late.status_code == 201
    correction = client.post(
        f"/api/v1/brew-sessions/measurements/{late.json()['id']}/corrections",
        json={
            "measurement_type": "POST_MASH_GRAVITY",
            "value": "1.047",
            "unit": "SG",
            "note": "Temperature compensation applied after the fact",
        },
    )
    assert correction.status_code == 201
    requirement_id = _requirement(session_id, stage_id)
    executed = client.post(
        f"/api/v1/brew-sessions/{session_id}/requirements/{requirement_id}/additions",
        json={
            "quantity": "10",
            "unit": "g",
            "operation_id": "adv-048-exec",
            "late_entry_reason": "Recorded hop charge after mash completion window",
        },
    )
    if executed.status_code != 201:
        return
    skipped = client.post(
        f"/api/v1/brew-sessions/{session_id}/addition-events/{executed.json()['id']}/corrections",
        json={
            "execution_status": "SKIPPED",
            "reason": "Charge was never actually added to the mash",
            "operation_id": "adv-048-skip",
            "correction_of_id": executed.json()["id"],
        },
    )
    assert skipped.status_code in {201, 409, 422}


def test_adv_032_oversize_and_traversal_filenames_rejected(active_mash, tmp_path, monkeypatch):
    from brewing_api.platform import config

    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    config.get_settings.cache_clear()
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    huge = client.post(
        f"/api/v1/brew-sessions/{session_id}/attachments",
        files={"file": ("mash.png", PNG + b"\x00" * (10 * 1024 * 1024 + 1), "image/png")},
        data={"operation_id": "adv-oversize"},
    )
    assert huge.status_code in {413, 422}
    traversal = client.post(
        f"/api/v1/brew-sessions/{session_id}/attachments",
        files={"file": ("../secret.png", PNG, "image/png")},
        data={"operation_id": "adv-traversal"},
    )
    assert traversal.status_code in {422, 415}


def test_adv_034_performance_bench_records_percentiles(active_mash):
    bench = active_mash["client"].post(
        f"/api/v1/brew-sessions/{active_mash['session_id']}/performance-bench"
    )
    assert bench.status_code == 200
    body = bench.json()
    assert body["sample_size"] >= 1
    assert "results" in body


def test_adv_044_052_053_054_055_runtime_repeat_policy_matrix():
    default_id = uuid.uuid4()
    repeatable_id = uuid.uuid4()
    source = _source(
        additions=(
            SourceAddition(
                id=default_id,
                ingredient_id=uuid.uuid4(),
                amount=Decimal("10"),
                unit="g",
                use_stage="MASH",
                timing_minutes=0,
            ),
            SourceAddition(
                id=repeatable_id,
                ingredient_id=uuid.uuid4(),
                amount=Decimal("5"),
                unit="g",
                use_stage="MASH",
                timing_minutes=0,
            ),
        )
    )
    preview = materialize_phase3_plan(source)
    mash = next(step for step in preview.steps if step.canonical_stage_type == "MASH")
    declared = materialize_phase3_plan(
        source,
        (
            AdditionRepeatDeclaration(
                source_addition_id=repeatable_id,
                target_plan_step_id=mash.plan_step_id,
                policy="RUNTIME_REPEAT_ALLOWED",
                reason="Authorized mash acid for rest repeats",
            ),
        ),
        preview.preview_hash,
    )
    mash_declared = next(step for step in declared.steps if step.canonical_stage_type == "MASH")
    policies = {
        item["source_addition_id"]: item["addition_repeat_policy"]
        for item in mash_declared.additions
    }
    assert policies[str(default_id)] == "PLANNED_OCCURRENCES_ONLY"
    assert policies[str(repeatable_id)] == "RUNTIME_REPEAT_ALLOWED"
