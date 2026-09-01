from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.domain.brew_day.canonical import canonical_json, sha256_hex
from brewing_api.domain.fermentation.constants import OPERATION_SCHEMA_VERSION
from brewing_api.domain.fermentation.models import FermentationOperation
from brewing_api.platform.time import utc_now


def operation_fingerprint(document: dict[str, Any]) -> str:
    return sha256_hex(
        canonical_json({"command_schema_version": OPERATION_SCHEMA_VERSION, **document})
    )


def lookup_operation(
    db: Session,
    actor_id: uuid.UUID,
    use_case: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    operation_id: str,
) -> FermentationOperation | None:
    return db.scalar(
        select(FermentationOperation).where(
            FermentationOperation.actor_user_id == actor_id,
            FermentationOperation.use_case == use_case,
            FermentationOperation.aggregate_type == aggregate_type,
            FermentationOperation.aggregate_id == aggregate_id,
            FermentationOperation.operation_id == operation_id,
        )
    )


def persist_operation(
    db: Session,
    actor_id: uuid.UUID,
    use_case: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    operation_id: str,
    fingerprint: str,
    http_status: int,
    result: dict[str, Any],
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    terminal: bool = False,
) -> FermentationOperation:
    now = utc_now()
    row = FermentationOperation(
        actor_user_id=actor_id,
        use_case=use_case,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        operation_id=operation_id,
        fingerprint=fingerprint,
        command_schema_version=OPERATION_SCHEMA_VERSION,
        http_status=http_status,
        result_resource_type=resource_type,
        result_resource_id=resource_id,
        result_payload=result,
        tombstone=True,
        completed_at=now,
        retained_until=None if not terminal else now + timedelta(days=90),
    )
    db.add(row)
    return row


def replay_or_conflict(
    db: Session,
    actor_id: uuid.UUID,
    use_case: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    operation_id: str | None,
    document: dict[str, Any],
) -> FermentationOperation | None:
    if not operation_id:
        raise DomainError("operation_id is required", 422, code="OPERATION_ID_REQUIRED")
    if len(operation_id) > 64:
        raise DomainError(
            "operation_id must be at most 64 characters", 422, code="INVALID_OPERATION_ID"
        )
    fingerprint = operation_fingerprint(document)
    existing = lookup_operation(db, actor_id, use_case, aggregate_type, aggregate_id, operation_id)
    if existing is None:
        return None
    if existing.fingerprint != fingerprint:
        raise ConflictError(
            "Idempotency key was reused with a different payload",
            code="IDEMPOTENCY_KEY_REUSED",
        )
    if (
        existing.retained_until
        and existing.retained_until < utc_now()
        and existing.tombstone
        and not existing.result_payload
    ):
        raise DomainError(
            "Idempotent result has been archived",
            410,
            code="IDEMPOTENT_RESULT_ARCHIVED",
            extra={
                "resource_id": str(existing.result_resource_id)
                if existing.result_resource_id
                else None
            },
        )
    return existing


def store_success(
    db: Session,
    actor_id: uuid.UUID,
    use_case: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    operation_id: str,
    document: dict[str, Any],
    result: dict[str, Any],
    resource_type: str,
    resource_id: uuid.UUID,
    http_status: int = 200,
    terminal: bool = False,
) -> FermentationOperation:
    fingerprint = operation_fingerprint(document)
    return persist_operation(
        db,
        actor_id,
        use_case,
        aggregate_type,
        aggregate_id,
        operation_id,
        fingerprint,
        http_status,
        result,
        resource_type,
        resource_id,
        terminal=terminal,
    )
