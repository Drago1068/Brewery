"""Append-only idempotency ledger helpers (ADR-006)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IdempotencyRecord
from app.domain.brew_day import json_safe


def fingerprint_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def lookup_idempotency(
    db: AsyncSession,
    *,
    scope_type: str,
    scope_id: str,
    client_submission_id: str,
) -> Optional[IdempotencyRecord]:
    result = await db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope_type == scope_type,
            IdempotencyRecord.scope_id == scope_id,
            IdempotencyRecord.client_submission_id == client_submission_id,
        )
    )
    return result.scalar_one_or_none()


def resolve_idempotency_or_conflict(
    existing: Optional[IdempotencyRecord],
    *,
    operation_type: str,
    request_fingerprint: str,
) -> Optional[dict]:
    """Return recorded response snapshot for exact replay, else None to proceed.

    Raises 409 IDEMPOTENCY_CONFLICT when same submission id was used with a
    different fingerprint or operation.
    """
    if existing is None:
        return None
    if (
        existing.operation_type == operation_type
        and existing.request_fingerprint == request_fingerprint
    ):
        return existing.response_snapshot
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "IDEMPOTENCY_CONFLICT",
            "message": "client_submission_id was already used with a different request",
            "existing_operation_type": existing.operation_type,
            "existing_resource_type": existing.resource_type,
            "existing_resource_id": existing.resource_id,
        },
    )


async def record_idempotency(
    db: AsyncSession,
    *,
    scope_type: str,
    scope_id: str,
    client_submission_id: str,
    operation_type: str,
    request_fingerprint: str,
    resource_type: str,
    resource_id: str,
    http_status: int,
    response_snapshot: dict,
    actor_id: str,
    session_version_before: Optional[int] = None,
    session_version_after: Optional[int] = None,
) -> IdempotencyRecord:
    row = IdempotencyRecord(
        scope_type=scope_type,
        scope_id=scope_id,
        client_submission_id=client_submission_id,
        operation_type=operation_type,
        request_fingerprint=request_fingerprint,
        resource_type=resource_type,
        resource_id=resource_id,
        http_status=http_status,
        response_snapshot=json_safe(response_snapshot),
        session_version_before=session_version_before,
        session_version_after=session_version_after,
        actor_id=actor_id,
    )
    db.add(row)
    return row
