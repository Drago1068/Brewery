from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: str,
    summary: str,
    brewery_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> AuditEvent:
    event = AuditEvent(
        brewery_id=brewery_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        summary=summary,
        details=details,
    )
    db.add(event)
    return event
