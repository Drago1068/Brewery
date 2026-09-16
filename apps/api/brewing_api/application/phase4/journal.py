"""Phase 4 journal merge, projection, and order fingerprint (P4-FR-062/063, AC-046, ADV-019)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.domain.audit.models import BrewJournalEvent
from brewing_api.domain.fermentation.constants import JOURNAL_SCHEMA_VERSION
from brewing_api.domain.fermentation.models import (
    FermentationJournalEvent,
    FermentationSession,
)
from brewing_api.platform.time import utc_now


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _sort_key(entry: dict[str, Any]) -> tuple:
    occurred = entry.get("_occurred_sort")
    recorded = entry.get("_recorded_sort")
    created = entry.get("_created_sort")
    # coalesce(occurred_at, recorded_at, created_at) for null-safe merge key
    occurred_key = occurred or recorded or created
    recorded_key = recorded or created
    return (occurred_key, recorded_key, entry["id"])


def append_journal_event(
    db: Session,
    session_id: uuid.UUID,
    event_type: str,
    message: str,
    *,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
    stage_id: uuid.UUID | None = None,
    occurred_at: datetime | None = None,
    event_data: dict | None = None,
    schema_version: str = JOURNAL_SCHEMA_VERSION,
) -> FermentationJournalEvent:
    now = utc_now()
    row = FermentationJournalEvent(
        fermentation_session_id=session_id,
        fermentation_stage_id=stage_id,
        event_type=event_type,
        message=message,
        event_data=event_data or {},
        schema_version=schema_version,
        occurred_at=occurred_at or now,
        recorded_at=now,
        actor_user_id=actor_id,
        operation_id=operation_id,
    )
    db.add(row)
    return row


def list_fermentation_journal_events(
    db: Session, session_id: uuid.UUID
) -> list[FermentationJournalEvent]:
    rows = list(
        db.scalars(
            select(FermentationJournalEvent).where(
                FermentationJournalEvent.fermentation_session_id == session_id
            )
        ).all()
    )
    rows.sort(
        key=lambda row: (
            row.occurred_at or row.recorded_at or row.created_at,
            row.recorded_at or row.created_at,
            row.id,
        )
    )
    return rows


def _normalize_phase3(row: BrewJournalEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "source_domain": "PHASE3",
        "event_type": row.event_type,
        "message": row.message,
        "event_data": row.event_data or {},
        "schema_version": row.schema_version,
        "occurred_at": _iso(row.occurred_at),
        "recorded_at": _iso(row.recorded_at),
        "created_at": _iso(row.created_at),
        "actor_user_id": None if row.actor_user_id is None else str(row.actor_user_id),
        "operation_id": row.operation_id,
        "stage_id": None if row.brew_stage_id is None else str(row.brew_stage_id),
        "_occurred_sort": row.occurred_at,
        "_recorded_sort": row.recorded_at,
        "_created_sort": row.created_at,
    }


def _normalize_phase4(row: FermentationJournalEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "source_domain": "PHASE4",
        "event_type": row.event_type,
        "message": row.message,
        "event_data": row.event_data or {},
        "schema_version": row.schema_version,
        "occurred_at": _iso(row.occurred_at),
        "recorded_at": _iso(row.recorded_at),
        "created_at": _iso(row.created_at),
        "actor_user_id": None if row.actor_user_id is None else str(row.actor_user_id),
        "operation_id": row.operation_id,
        "stage_id": None if row.fermentation_stage_id is None else str(row.fermentation_stage_id),
        "_occurred_sort": row.occurred_at,
        "_recorded_sort": row.recorded_at,
        "_created_sort": row.created_at,
    }


def merged_journal_events(
    db: Session, fermentation_session: FermentationSession
) -> list[dict[str, Any]]:
    phase3 = list(
        db.scalars(
            select(BrewJournalEvent).where(
                BrewJournalEvent.brew_session_id == fermentation_session.brew_session_id
            )
        ).all()
    )
    phase4 = list(
        db.scalars(
            select(FermentationJournalEvent).where(
                FermentationJournalEvent.fermentation_session_id == fermentation_session.id
            )
        ).all()
    )
    merged = [_normalize_phase3(row) for row in phase3] + [_normalize_phase4(row) for row in phase4]
    merged.sort(key=_sort_key)
    return [serialize_journal_entry(entry) for entry in merged]


def serialize_journal_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry["id"],
        "source_domain": entry["source_domain"],
        "event_type": entry["event_type"],
        "message": entry["message"],
        "event_data": entry.get("event_data") or {},
        "schema_version": entry.get("schema_version"),
        "occurred_at": entry.get("occurred_at"),
        "recorded_at": entry.get("recorded_at"),
        "created_at": entry.get("created_at"),
        "actor_user_id": entry.get("actor_user_id"),
        "operation_id": entry.get("operation_id"),
        "stage_id": entry.get("stage_id"),
    }


def journal_order_fingerprint(entries: list[dict[str, Any]]) -> str:
    lines = [f"{item['source_domain']}:{item['id']}" for item in entries]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
