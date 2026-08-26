import uuid

from sqlalchemy import select

from brewing_api.domain.brew_day.models import BrewPlanStep, BrewRequirementTemplate
from brewing_api.domain.brew_sessions.models import BrewSession
from brewing_api.platform.database import SessionLocal


def test_phase1a_recipe_materializes_legacy_plan(authenticated_client, recipe_payload):
    recipe = authenticated_client.post("/api/v1/recipes", json=recipe_payload).json()
    preview = authenticated_client.get(
        f"/api/v1/recipe-versions/{recipe['version_id']}/phase3-plan-preview"
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["plan_kind"] == "LEGACY_MASH_ONLY"
    assert [step["canonical_stage_type"] for step in body["steps"]] == ["MASH", "BREW_COMPLETE"]

    created = authenticated_client.post(
        "/api/v1/brew-sessions",
        json={
            "recipe_version_id": recipe["version_id"],
            "operation_id": str(uuid.uuid4()),
        },
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    with SessionLocal() as db:
        session = db.get(BrewSession, uuid.UUID(session_id))
        assert session.plan_kind == "LEGACY_MASH_ONLY"
        steps = list(
            db.scalars(select(BrewPlanStep).where(BrewPlanStep.brew_session_id == session.id))
        )
        assert {item.canonical_stage_type for item in steps} == {"MASH", "BREW_COMPLETE"}
        templates = list(
            db.scalars(
                select(BrewRequirementTemplate).where(
                    BrewRequirementTemplate.brew_session_id == session.id
                )
            )
        )
        assert any(item.definition_key == "MASH_PH" for item in templates)


def test_pause_resume_abort_and_note(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    command = active_mash["command"]
    paused = client.post(f"/api/v1/brew-sessions/{session_id}/pause", json=command())
    assert paused.status_code == 200
    assert paused.json()["status"] == "PAUSED"
    resumed = client.post(f"/api/v1/brew-sessions/{session_id}/resume", json=command())
    assert resumed.json()["status"] == "ACTIVE"
    note = client.post(
        f"/api/v1/brew-sessions/{session_id}/notes",
        json=command(body="Iodine rest looked complete after stirring."),
    )
    assert note.status_code == 201
    aborted = client.post(
        f"/api/v1/brew-sessions/{session_id}/abort",
        json=command(reason="Boil kettle failure forced a stop"),
    )
    assert aborted.status_code == 200
    assert aborted.json()["status"] == "ABORTED"
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    assert details["status"] == "ABORTED"
    assert details["notes"][0]["body"].startswith("Iodine")


def test_reminder_acknowledgement_does_not_complete_requirement(active_mash):
    client = active_mash["client"]
    command = active_mash["command"]
    details = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}").json()
    reminder_id = details["mash"]["notifications"][0]["id"]
    ack = client.post(
        f"/api/v1/brew-sessions/reminders/{reminder_id}/acknowledge",
        json=command(),
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "ACKNOWLEDGED"
    after = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}").json()
    assert after["mash"]["notifications"][0]["status"] == "ACKNOWLEDGED"
    complete = client.post(
        f"/api/v1/brew-sessions/stages/{active_mash['stage_id']}/complete",
        json=command(),
    )
    assert complete.status_code == 400


def test_csrf_rejects_missing_token(client, recipe_payload):
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "brewer", "password": "test-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers.pop("X-CSRF-Token", None)
    response = client.post("/api/v1/recipes", json=recipe_payload)
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_REJECTED"


def test_completion_audit_endpoint(active_mash):
    client = active_mash["client"]
    audit = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}/completion-audit")
    assert audit.status_code == 200
    assert audit.json()["rule_version"] == "phase3-completion-audit-v1"
    assert audit.json()["measurement_completeness_excludes_waivers"] is True
