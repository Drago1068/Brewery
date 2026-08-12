import uuid

from sqlalchemy.orm import Session

from brewing_api.domain.audit.models import AuditEvent, BrewJournalEvent


def audit(
    db: Session,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    details: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
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
) -> BrewJournalEvent:
    event = BrewJournalEvent(
        brew_session_id=session_id,
        brew_stage_id=stage_id,
        event_type=event_type,
        message=message,
        event_data=data or {},
    )
    db.add(event)
    return event

