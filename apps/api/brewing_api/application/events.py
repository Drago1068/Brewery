import uuid

from sqlalchemy.orm import Session

from brewing_api.domain.audit.models import AuditEvent, BrewJournalEvent
from brewing_api.platform.time import utc_now


def audit(
    db: Session,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    details: dict | None = None,
    operation_id: str | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        operation_id=operation_id,
        correlation_id=correlation_id,
    )
    db.add(event)
    return event


def journal(
    db: Session,
    session_id: uuid.UUID,
    event_type: str,
    message: str,
    stage_id: uuid.UUID | None = None,
    data: dict | None = None,
    actor_id: uuid.UUID | None = None,
    operation_id: str | None = None,
) -> BrewJournalEvent:
    now = utc_now()
    event = BrewJournalEvent(
        brew_session_id=session_id,
        brew_stage_id=stage_id,
        event_type=event_type,
        message=message,
        event_data=data or {},
        occurred_at=now,
        recorded_at=now,
        actor_user_id=actor_id,
        operation_id=operation_id,
    )
    db.add(event)
    return event
