from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import DomainError
from brewing_api.domain.brew_day.models import BrewPitchHandoff
from brewing_api.domain.brew_sessions.models import BrewSession
from brewing_api.domain.fermentation.models import FermentationSession
from brewing_api.domain.identity.models import User


def get_owned_brew_session(db: Session, user: User, brew_session_id: uuid.UUID) -> BrewSession:
    session = db.get(BrewSession, brew_session_id)
    if session is None or session.user_id != user.id:
        raise DomainError("Brew session not found", 404)
    return session


def get_fermentation_session(
    db: Session, user: User, fermentation_session_id: uuid.UUID
) -> FermentationSession:
    found = db.get(FermentationSession, fermentation_session_id)
    if found is None or found.user_id != user.id:
        raise DomainError("Fermentation session not found", 404)
    return found


def get_active_fermentation_for_brew(
    db: Session, brew_session_id: uuid.UUID
) -> FermentationSession | None:
    return db.scalar(
        select(FermentationSession).where(
            FermentationSession.brew_session_id == brew_session_id,
            FermentationSession.status != "ABORTED",
        )
    )


def require_pitch_handoff(db: Session, brew_session_id: uuid.UUID) -> BrewPitchHandoff:
    handoff = db.scalar(
        select(BrewPitchHandoff).where(BrewPitchHandoff.brew_session_id == brew_session_id)
    )
    if handoff is None:
        raise DomainError(
            "Phase 3 yeast pitch handoff is required before starting fermentation",
            422,
            code="PITCH_HANDOFF_REQUIRED",
        )
    return handoff
