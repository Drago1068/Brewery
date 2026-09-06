"""Slice 15 — JOURNAL_MEDIA_EXPORT (FR-062–065, AC-046/052, ADV-013/019)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import func, select

from brewing_api.application.auth import password_hash
from brewing_api.application.phase4.journal import journal_order_fingerprint
from brewing_api.domain.audit.models import BrewJournalEvent
from brewing_api.domain.fermentation.constants import JOURNAL_EVENT_TYPES
from brewing_api.domain.fermentation.models import (
    FermentationAttachment,
    FermentationJournalEvent,
    FermentationNote,
)
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now
from phase4_lifecycle_helpers import reach_fermentation_complete, skip_conditioning

pytestmark = pytest.mark.integration

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _jpeg_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (1, 1), (200, 40, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _revision(client, session_id: str) -> int:
    return client.get(f"/api/v1/fermentation-sessions/{session_id}").json()["revision"]


def _close_session(client, started: dict) -> dict:
    session_id = started["fermentation_session_id"]
    set_plan = reach_fermentation_complete(client, started)
    skipped = skip_conditioning(
        client,
        session_id=session_id,
        revision=set_plan["revision"],
    )
    assert skipped.status_code == 200, skipped.text
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
    closed = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/commands/close",
        json={
            "operation_id": str(uuid.uuid4()),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert closed.status_code == 200, closed.text
    return closed.json()


def _insert_phase3_journal(
    brew_session_id: str,
    *,
    event_type: str,
    message: str,
    occurred_at,
    recorded_at=None,
) -> uuid.UUID:
    event_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            BrewJournalEvent(
                id=event_id,
                brew_session_id=uuid.UUID(brew_session_id),
                event_type=event_type,
                message=message,
                event_data={},
                occurred_at=occurred_at,
                recorded_at=recorded_at or occurred_at,
            )
        )
        db.commit()
    return event_id


def test_fr063_closed_vocabulary_constant(started_fermentation):
    required = {
        "FERMENTATION_SESSION_STARTED",
        "FERMENTATION_MEASUREMENT_RECORDED",
        "FERMENTATION_MEASUREMENT_CORRECTED",
        "FERMENTATION_ACTION_RECORDED",
        "FERMENTATION_ADDITION_RECORDED",
        "CONDITIONING_STARTED",
        "PACKAGING_READINESS_ASSESSED",
        "PACKAGING_READINESS_HANDOFF_RECORDED",
        "YEAST_REFERENCE_RECORDED",
        "OG_CONSUMPTION_PINNED",
        "FERMENTATION_SESSION_CLOSED",
    }
    assert required <= JOURNAL_EVENT_TYPES
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    journal = client.get(f"/api/v1/fermentation-sessions/{session_id}/journal")
    assert journal.status_code == 200, journal.text
    types = {item["event_type"] for item in journal.json()["items"]}
    assert "FERMENTATION_SESSION_STARTED" in types
    export = client.get(f"/api/v1/fermentation-sessions/{session_id}/export?format=json")
    assert export.status_code == 200
    export_types = {
        item["event_type"] for item in export.json()["document"]["journal"]
    }
    assert "FERMENTATION_SESSION_STARTED" in export_types


def test_ac046_stable_export_order_hash(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    brew_id = started_fermentation["session_id"]
    # Keep process times after pitch so measurement corrections remain lawful.
    shared = utc_now() - timedelta(minutes=1)
    earlier = shared - timedelta(seconds=30)
    later = shared + timedelta(seconds=30)

    p3_early = _insert_phase3_journal(
        brew_id,
        event_type="BREW_STAGE_STARTED",
        message="early phase3",
        occurred_at=earlier,
    )
    p3_shared = _insert_phase3_journal(
        brew_id,
        event_type="BREW_NOTE_ADDED",
        message="phase3 shared stamp",
        occurred_at=shared,
        recorded_at=shared,
    )
    p3_late = _insert_phase3_journal(
        brew_id,
        event_type="BREW_MEDIA_ATTACHED",
        message="late phase3",
        occurred_at=later,
    )

    gravity = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements",
        json={
            "operation_id": str(uuid.uuid4()),
            "measurement_type": "FERMENTATION_GRAVITY",
            "value": "1.040",
            "unit": "SG",
            "observed_at": earlier.isoformat(),
            "stage_instance_id": started_fermentation["active_stage_id"],
            "method": "HYDROMETER",
            "sample_temperature_c": "20.00",
            "source": "OBSERVED",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert gravity.status_code == 201, gravity.text
    measurement_id = gravity.json()["id"]
    corrected = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/measurements/{measurement_id}/corrections",
        json={
            "operation_id": str(uuid.uuid4()),
            "correction_of_id": measurement_id,
            "reason": "Backdated correction for merge-key stability check",
            "value": "1.041",
            "unit": "SG",
            "observed_at": shared.isoformat(),
            "expected_revision": _revision(client, session_id),
        },
    )
    assert corrected.status_code == 201, corrected.text

    first = client.get(f"/api/v1/fermentation-sessions/{session_id}/export?format=json")
    second = client.get(f"/api/v1/fermentation-sessions/{session_id}/export?format=json")
    assert first.status_code == 200 and second.status_code == 200
    doc1 = first.json()["document"]
    doc2 = second.json()["document"]
    assert doc1["journal_order_fingerprint"] == doc2["journal_order_fingerprint"]
    assert journal_order_fingerprint(doc1["journal"]) == doc1["journal_order_fingerprint"]

    phase3_ids = [
        item["id"]
        for item in doc1["journal"]
        if item["source_domain"] == "PHASE3"
        and item["id"] in {str(p3_early), str(p3_shared), str(p3_late)}
    ]
    assert phase3_ids == [str(p3_early), str(p3_shared), str(p3_late)]

    shared_entries = [
        item
        for item in doc1["journal"]
        if item.get("occurred_at") and item["occurred_at"].startswith(shared.isoformat()[:19])
    ]
    assert any(item["source_domain"] == "PHASE3" for item in shared_entries)
    assert any(
        item["source_domain"] == "PHASE4"
        and item["event_type"] == "FERMENTATION_MEASUREMENT_CORRECTED"
        for item in shared_entries
    )


def test_adv019_backdated_correction_stable_merge(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    brew_id = started_fermentation["session_id"]
    shared = utc_now() - timedelta(hours=3)
    p3_id = _insert_phase3_journal(
        brew_id,
        event_type="BREW_STAGE_COMPLETED",
        message="phase3 peer",
        occurred_at=shared,
        recorded_at=shared,
    )
    with SessionLocal() as db:
        db.add(
            FermentationJournalEvent(
                fermentation_session_id=uuid.UUID(session_id),
                event_type="FERMENTATION_MEASUREMENT_CORRECTED",
                message="backdated correction",
                event_data={"synthetic": True},
                occurred_at=shared,
                recorded_at=utc_now(),
            )
        )
        db.commit()

    export_a = client.get(f"/api/v1/fermentation-sessions/{session_id}/export?format=json")
    export_b = client.get(f"/api/v1/fermentation-sessions/{session_id}/export?format=json")
    assert export_a.status_code == 200 and export_b.status_code == 200
    fp_a = export_a.json()["document"]["journal_order_fingerprint"]
    fp_b = export_b.json()["document"]["journal_order_fingerprint"]
    assert fp_a == fp_b
    ids = [item["id"] for item in export_a.json()["document"]["journal"]]
    assert str(p3_id) in ids
    assert ids == [item["id"] for item in export_b.json()["document"]["journal"]]


def test_ac052_malformed_media_rejected(started_fermentation, tmp_path, monkeypatch):
    from brewing_api.platform import config

    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    config.get_settings.cache_clear()
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    before = 0
    with SessionLocal() as db:
        before = db.scalar(
            select(func.count()).select_from(FermentationAttachment).where(
                FermentationAttachment.fermentation_session_id == uuid.UUID(session_id)
            )
        )
    rejected = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/attachments",
        files={"file": ("evil.html", b"<html><body>nope</body></html>", "text/html")},
        data={"operation_id": str(uuid.uuid4())},
    )
    assert rejected.status_code in {415, 422}, rejected.text
    with SessionLocal() as db:
        after = db.scalar(
            select(func.count()).select_from(FermentationAttachment).where(
                FermentationAttachment.fermentation_session_id == uuid.UUID(session_id)
            )
        )
    assert after == before


def test_adv013_polyglot_mime_mismatch(started_fermentation, tmp_path, monkeypatch):
    from brewing_api.platform import config

    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    config.get_settings.cache_clear()
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    png_as_jpeg = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/attachments",
        files={"file": ("lie.jpg", PNG, "image/jpeg")},
        data={"operation_id": str(uuid.uuid4())},
    )
    assert png_as_jpeg.status_code in {415, 422}, png_as_jpeg.text
    html_as_jpeg = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/attachments",
        files={"file": ("lie.jpg", b"<html>polyglot</html>", "image/jpeg")},
        data={"operation_id": str(uuid.uuid4())},
    )
    assert html_as_jpeg.status_code in {415, 422}, html_as_jpeg.text


def test_fr064_note_and_media_happy_path(started_fermentation, tmp_path, monkeypatch):
    from brewing_api.platform import config

    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    config.get_settings.cache_clear()
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    note = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/notes",
        json={
            "operation_id": str(uuid.uuid4()),
            "body": "Krausen looks healthy",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert note.status_code == 201, note.text
    jpeg = _jpeg_bytes()
    uploaded = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/attachments",
        files={"file": ("ferment.jpg", jpeg, "image/jpeg")},
        data={"operation_id": str(uuid.uuid4()), "caption": "day 2"},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["id"]
    listed = client.get(f"/api/v1/fermentation-sessions/{session_id}/attachments")
    assert listed.status_code == 200
    assert any(item["id"] == attachment_id for item in listed.json()["items"])
    fetched = client.get(
        f"/api/v1/fermentation-sessions/{session_id}/attachments/{attachment_id}"
    )
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/jpeg"
    assert fetched.content[:3] == b"\xff\xd8\xff"
    details = client.get(f"/api/v1/fermentation-sessions/{session_id}").json()
    assert any(item["id"] == note.json()["id"] for item in details["notes"])
    assert any(item["id"] == attachment_id for item in details["attachments"])


def test_fr064_terminal_media_upload_denied(started_fermentation, tmp_path, monkeypatch):
    from brewing_api.platform import config

    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    config.get_settings.cache_clear()
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    _close_session(client, started_fermentation)
    denied = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/attachments",
        files={"file": ("too-late.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"operation_id": str(uuid.uuid4())},
    )
    assert denied.status_code == 409, denied.text


def test_fr065_export_json_html(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    client.post(
        f"/api/v1/fermentation-sessions/{session_id}/notes",
        json={
            "operation_id": str(uuid.uuid4()),
            "body": "Export note body",
            "expected_revision": _revision(client, session_id),
        },
    )
    json_export = client.get(
        f"/api/v1/fermentation-sessions/{session_id}/export?format=json"
    )
    assert json_export.status_code == 200
    document = json_export.json()["document"]
    assert "journal" in document
    assert "notes" in document
    assert "attachments" in document
    assert "fermentation_assessments" in document
    assert "conditioning_assessments" in document
    assert "packaging_assessments" in document
    assert "packaging_readiness_handoffs" in document
    assert "completion_assessment" in document
    assert "packaging_readiness_handoff" in document

    html_export = client.get(
        f"/api/v1/fermentation-sessions/{session_id}/export?format=html"
    )
    assert html_export.status_code == 200
    body = html_export.json()
    assert body["format"] == "html"
    assert "occurred=" in body["html"]
    assert "recorded=" in body["html"]
    assert "Export note body" in body["html"]


def test_ownership_export_404(started_fermentation, client):
    session_id = started_fermentation["fermentation_session_id"]
    with SessionLocal() as db:
        db.add(
            User(
                username="other-export-user",
                password_hash=password_hash.hash("other-password-not-a-secret"),
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "other-export-user", "password": "other-password-not-a-secret"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    denied = client.get(f"/api/v1/fermentation-sessions/{session_id}/export?format=json")
    assert denied.status_code == 404, denied.text


def test_idempotent_note_replay(started_fermentation):
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    operation_id = str(uuid.uuid4())
    payload = {
        "operation_id": operation_id,
        "body": "Idempotent note body",
        "expected_revision": _revision(client, session_id),
    }
    first = client.post(f"/api/v1/fermentation-sessions/{session_id}/notes", json=payload)
    assert first.status_code == 201, first.text
    second = client.post(f"/api/v1/fermentation-sessions/{session_id}/notes", json=payload)
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    with SessionLocal() as db:
        count = db.scalar(
            select(func.count()).select_from(FermentationNote).where(
                FermentationNote.fermentation_session_id == uuid.UUID(session_id),
                FermentationNote.operation_id == operation_id,
            )
        )
    assert count == 1


def test_recovery_reread_note_media(started_fermentation, tmp_path, monkeypatch):
    from brewing_api.platform import config

    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    config.get_settings.cache_clear()
    client = started_fermentation["client"]
    session_id = started_fermentation["fermentation_session_id"]
    note = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/notes",
        json={
            "operation_id": str(uuid.uuid4()),
            "body": "Recoverable note",
            "expected_revision": _revision(client, session_id),
        },
    )
    assert note.status_code == 201, note.text
    uploaded = client.post(
        f"/api/v1/fermentation-sessions/{session_id}/attachments",
        files={"file": ("recover.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"operation_id": str(uuid.uuid4())},
    )
    assert uploaded.status_code == 201, uploaded.text
    reread = client.get(f"/api/v1/fermentation-sessions/{session_id}")
    assert reread.status_code == 200
    body = reread.json()
    assert any(item["id"] == note.json()["id"] for item in body["notes"])
    assert any(item["id"] == uploaded.json()["id"] for item in body["attachments"])
    listed = client.get(f"/api/v1/fermentation-sessions/{session_id}/attachments")
    assert listed.status_code == 200
    assert listed.json()["items"]
