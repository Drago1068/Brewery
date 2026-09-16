"""Phase 4 fermentation export JSON/HTML (P4-FR-065, AC-046, ADV-019)."""

from __future__ import annotations

import html
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import DomainError
from brewing_api.application.phase4.completion import serialize_assessment
from brewing_api.application.phase4.journal import (
    journal_order_fingerprint,
    merged_journal_events,
)
from brewing_api.application.phase4.media import (
    attachment_bytes_available,
    list_session_attachments,
    serialize_attachment,
)
from brewing_api.application.phase4.notes import list_session_notes, serialize_note
from brewing_api.application.phase4.read_models import serialize_session
from brewing_api.application.phase4.readiness import serialize_handoff
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.domain.fermentation.models import (
    FermentationCompletionAssessment,
    PackagingReadinessHandoff,
)
from brewing_api.domain.identity.models import User


def _assessments_by_kind(db: Session, session_id: uuid.UUID, kind: str) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(FermentationCompletionAssessment)
            .where(
                FermentationCompletionAssessment.fermentation_session_id == session_id,
                FermentationCompletionAssessment.assessment_kind == kind,
            )
            .order_by(
                FermentationCompletionAssessment.assessed_at,
                FermentationCompletionAssessment.created_at,
                FermentationCompletionAssessment.id,
            )
        ).all()
    )
    return [serialize_assessment(row) for row in rows]


def _all_handoffs(db: Session, session_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(PackagingReadinessHandoff)
            .where(PackagingReadinessHandoff.fermentation_session_id == session_id)
            .order_by(
                PackagingReadinessHandoff.handoff_version,
                PackagingReadinessHandoff.created_at,
                PackagingReadinessHandoff.id,
            )
        ).all()
    )
    return [serialize_handoff(row) for row in rows]


def build_export_document(db: Session, user: User, session_id: uuid.UUID) -> dict[str, Any]:
    document = serialize_session(db, user, session_id)
    session = get_fermentation_session(db, user, session_id)
    journal = merged_journal_events(db, session)
    notes = [serialize_note(item) for item in list_session_notes(db, session.id)]
    attachments = [serialize_attachment(item) for item in list_session_attachments(db, session.id)]
    document["journal"] = journal
    document["notes"] = notes
    document["attachments"] = attachments
    document["journal_order_fingerprint"] = journal_order_fingerprint(journal)
    document["fermentation_assessments"] = _assessments_by_kind(db, session.id, "FERMENTATION")
    document["conditioning_assessments"] = _assessments_by_kind(db, session.id, "CONDITIONING")
    document["packaging_assessments"] = _assessments_by_kind(db, session.id, "PACKAGING")
    document["packaging_readiness_handoffs"] = _all_handoffs(db, session.id)
    return document


def export_json(db: Session, user: User, session_id: uuid.UUID) -> dict[str, Any]:
    return {"format": "json", "document": build_export_document(db, user, session_id)}


def _render_journal_html(entries: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in entries:
        occurred = html.escape(str(item.get("occurred_at") or ""))
        recorded = html.escape(str(item.get("recorded_at") or ""))
        message = html.escape(str(item.get("message") or ""))
        event_type = html.escape(str(item.get("event_type") or ""))
        source = html.escape(str(item.get("source_domain") or ""))
        rows.append(
            "<li>"
            f"<span class='source'>{source}</span> "
            f"<span class='type'>{event_type}</span> "
            f"<span class='occurred'>occurred={occurred}</span> "
            f"<span class='recorded'>recorded={recorded}</span> "
            f"{message}"
            "</li>"
        )
    return "<ol>" + "".join(rows) + "</ol>"


def _render_attachments_html(attachments: list[dict[str, Any]], db: Session) -> str:
    from brewing_api.domain.fermentation.models import FermentationAttachment

    rows: list[str] = []
    for item in attachments:
        caption = html.escape(str(item.get("caption") or item.get("original_filename") or ""))
        attachment_id = item.get("id")
        available = item.get("bytes_available")
        if available is False:
            rows.append(
                f"<li>{caption} "
                f"<span class='media-unavailable'>MEDIA_UNAVAILABLE</span> "
                f"(id={html.escape(str(attachment_id))})</li>"
            )
            continue
        if available is None and attachment_id:
            row = db.get(FermentationAttachment, uuid.UUID(str(attachment_id)))
            if row is not None and not attachment_bytes_available(row):
                rows.append(
                    f"<li>{caption} "
                    f"<span class='media-unavailable'>MEDIA_UNAVAILABLE</span> "
                    f"(id={html.escape(str(attachment_id))})</li>"
                )
                continue
        rows.append(f"<li>{caption} (id={html.escape(str(attachment_id))})</li>")
    return "<ul>" + "".join(rows) + "</ul>"


def export_html(db: Session, user: User, session_id: uuid.UUID) -> dict[str, Any]:
    document = build_export_document(db, user, session_id)
    title = html.escape(f"Fermentation export {session_id}")
    journal_html = _render_journal_html(document.get("journal") or [])
    notes_html = "".join(
        f"<li>{html.escape(str(note.get('body') or ''))}</li>"
        for note in (document.get("notes") or [])
    )
    attachments_html = _render_attachments_html(document.get("attachments") or [], db)
    body = (
        f"<html><body><h1>{title}</h1>"
        f"<h2>Journal</h2>{journal_html}"
        f"<h2>Notes</h2><ul>{notes_html}</ul>"
        f"<h2>Attachments</h2>{attachments_html}"
        f"<h2>Assessments</h2>"
        f"<p>fermentation={len(document.get('fermentation_assessments') or [])} "
        f"conditioning={len(document.get('conditioning_assessments') or [])} "
        f"packaging={len(document.get('packaging_assessments') or [])} "
        f"handoffs={len(document.get('packaging_readiness_handoffs') or [])}</p>"
        "</body></html>"
    )
    return {"format": "html", "html": body, "document": document}


def export_session(
    db: Session, user: User, session_id: uuid.UUID, format: str = "json"
) -> dict[str, Any]:
    if format == "html":
        return export_html(db, user, session_id)
    if format == "json":
        return export_json(db, user, session_id)
    raise DomainError("Unsupported export format", 422, code="UNSUPPORTED_EXPORT_FORMAT")
