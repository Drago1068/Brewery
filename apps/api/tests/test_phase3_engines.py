import time
import uuid
from datetime import timedelta

from sqlalchemy import select

from brewing_api.application.auth import password_hash
from brewing_api.application.phase3.additions import inventory_transaction_count
from brewing_api.application.phase3.voice import parse_voice_proposal
from brewing_api.domain.brew_day.models import BrewStageRequirement, BrewTimerRevision
from brewing_api.domain.brew_sessions.models import BrewTimer
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _requirement(session_id: str, stage_id: str) -> uuid.UUID:
    requirement_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            BrewStageRequirement(
                brew_session_id=uuid.UUID(session_id),
                stage_instance_id=uuid.UUID(stage_id),
                requirement_template_id=uuid.uuid4(),
                requirement_class="ADDITION",
                requirement_id=requirement_id,
                required=True,
                waivable=True,
                payload={
                    "definition_key": "MASH_ADDITION",
                    "planned_amount": "10",
                    "planned_unit": "g",
                    "timing_basis": "UNSCHEDULED",
                    "source_addition_id": str(uuid.uuid4()),
                },
            )
        )
        db.commit()
    return requirement_id


def test_voice_proposal_is_not_a_commit():
    proposal = parse_voice_proposal("five point two pH")
    assert proposal is not None
    assert proposal["value"] == "5.2"
    assert proposal["committed"] == "false"
    assert parse_voice_proposal("fifty two")["value"] == "52"


def test_idempotent_pause_replays_same_result(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    first = client.post(
        f"/api/v1/brew-sessions/{session_id}/pause",
        json={"operation_id": "pause-1"},
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/v1/brew-sessions/{session_id}/pause",
        json={"operation_id": "pause-1"},
    )
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    conflict = client.post(
        f"/api/v1/brew-sessions/{session_id}/pause",
        json={"operation_id": "pause-1", "expected_revision": 99},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_stale_revision_is_conflict(active_mash):
    client = active_mash["client"]
    details = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}").json()
    response = client.post(
        f"/api/v1/brew-sessions/{active_mash['session_id']}/pause",
        json={"expected_revision": details["revision"] - 1},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "STALE_REVISION"


def test_timer_replace_preserves_original_identity(active_mash):
    client = active_mash["client"]
    details = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}").json()
    timer_id = details["timers"][0]["id"]
    replaced = client.post(
        f"/api/v1/brew-sessions/timers/{timer_id}/replace",
        json={"reason": "Probe failed and timer purpose changed", "planned_duration_seconds": 90},
    )
    assert replaced.status_code == 200
    after = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}").json()
    assert after["timers"][0]["id"] == timer_id or any(
        item["id"] == replaced.json()["id"] for item in after["timers"]
    )
    with SessionLocal() as db:
        original = db.get(BrewTimer, uuid.UUID(timer_id))
        assert original.status == "CANCELLED"
        assert original.cancel_reason.startswith("REPLACED")


def test_timer_extend_appends_revision(active_mash):
    client = active_mash["client"]
    details = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}").json()
    timer_id = details["timers"][0]["id"]
    response = client.post(
        f"/api/v1/brew-sessions/timers/{timer_id}/extend",
        json={"extra_seconds": 30, "reason": "mash rest needed more conversion time"},
    )
    assert response.status_code == 200
    with SessionLocal() as db:
        revisions = list(
            db.scalars(
                select(BrewTimerRevision).where(BrewTimerRevision.timer_id == uuid.UUID(timer_id))
            )
        )
        assert len(revisions) == 1
        timer = db.get(BrewTimer, uuid.UUID(timer_id))
        assert timer.planned_duration_seconds >= 90


def test_expired_timer_survives_reconnect(active_mash):
    client = active_mash["client"]
    details = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}").json()
    timer_id = uuid.UUID(details["timers"][0]["id"])
    with SessionLocal() as db:
        timer = db.get(BrewTimer, timer_id)
        timer.deadline_at = utc_now() - timedelta(seconds=5)
        db.commit()
    recovered = client.get(f"/api/v1/brew-sessions/{active_mash['session_id']}").json()
    assert recovered["timers"][0]["status"] == "EXPIRED"
    ack = client.post(f"/api/v1/brew-sessions/timers/{timer_id}/acknowledge")
    assert ack.json()["status"] == "ACKNOWLEDGED"


def test_addition_execution_has_zero_inventory_effect(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    requirement_id = _requirement(session_id, active_mash["stage_id"])
    with SessionLocal() as db:
        before = inventory_transaction_count(db)
    executed = client.post(
        f"/api/v1/brew-sessions/{session_id}/requirements/{requirement_id}/additions",
        json={"quantity": "10", "unit": "g", "operation_id": "add-1"},
    )
    assert executed.status_code == 201
    replay = client.post(
        f"/api/v1/brew-sessions/{session_id}/requirements/{requirement_id}/additions",
        json={"quantity": "10", "unit": "g", "operation_id": "add-1"},
    )
    assert replay.json()["id"] == executed.json()["id"]
    with SessionLocal() as db:
        assert inventory_transaction_count(db) == before


def test_waiver_does_not_count_as_measurement(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    requirement_id = _requirement(session_id, active_mash["stage_id"])
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    waived = client.post(
        f"/api/v1/brew-sessions/{session_id}/requirements/{requirement_id}/waivers",
        json={
            "reason": "Could not verify hop charge visually",
            "operation_id": "waiver-1",
            "expected_revision": details["revision"],
        },
    )
    assert waived.status_code == 201
    audit = client.get(f"/api/v1/brew-sessions/{session_id}/completion-audit").json()
    assert audit["waived_count"] >= 1
    assert audit["measurement_completeness_excludes_waivers"] is True


def test_voice_proposal_endpoint_does_not_record_measurement(active_mash):
    client = active_mash["client"]
    parsed = client.post(
        "/api/v1/brew-sessions/voice/proposals",
        json={"transcript": "fifty two pH"},
    )
    assert parsed.status_code == 200
    assert parsed.json()["committed"] is False
    assert parsed.json()["proposal"]["value"] == "52"
    rejected = client.post(
        f"/api/v1/brew-sessions/stages/{active_mash['stage_id']}/measurements",
        json={"measurement_type": "MASH_PH", "value": "52", "unit": "pH"},
    )
    assert rejected.status_code == 422


def test_media_allowlist_and_headers(active_mash, tmp_path, monkeypatch):
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
        data={"operation_id": "media-bad"},
    )
    assert rejected.status_code in {415, 422}
    uploaded = client.post(
        f"/api/v1/brew-sessions/{session_id}/attachments",
        files={"file": ("mash.png", PNG, "image/png")},
        data={"operation_id": "media-1"},
    )
    assert uploaded.status_code == 201
    attachment_id = uploaded.json()["id"]
    fetched = client.get(f"/api/v1/brew-sessions/{session_id}/attachments/{attachment_id}")
    assert fetched.status_code == 200
    assert fetched.headers["x-content-type-options"] == "nosniff"
    assert fetched.headers["content-type"] == "image/png"
    assert "brew-photo-" in fetched.headers["content-disposition"]
    replay = client.post(
        f"/api/v1/brew-sessions/{session_id}/attachments",
        files={"file": ("mash.png", PNG, "image/png")},
        data={"operation_id": "media-1"},
    )
    assert replay.json()["id"] == attachment_id


def test_cross_owner_session_is_hidden(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    with SessionLocal() as db:
        db.add(
            User(
                username="other-brewer",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "other-brewer", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    hidden = client.get(f"/api/v1/brew-sessions/{session_id}")
    assert hidden.status_code == 404


def test_dashboard_projection_p95_under_threshold(active_mash):
    client = active_mash["client"]
    path = f"/api/v1/brew-sessions/{active_mash['session_id']}"
    samples = []
    for _ in range(20):
        started = time.perf_counter()
        response = client.get(path)
        samples.append((time.perf_counter() - started) * 1000)
        assert response.status_code == 200
    samples.sort()
    p95 = samples[int(0.95 * (len(samples) - 1))]
    assert p95 <= 750


def test_abort_blocks_new_measurement(active_mash):
    client = active_mash["client"]
    client.post(
        f"/api/v1/brew-sessions/{active_mash['session_id']}/abort",
        json={"reason": "Kettle failure forced an immediate stop"},
    )
    response = client.post(
        f"/api/v1/brew-sessions/stages/{active_mash['stage_id']}/measurements",
        json={"measurement_type": "MASH_PH", "value": "5.30", "unit": "pH"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "TERMINAL_SESSION_EVIDENCE_PROHIBITED"
