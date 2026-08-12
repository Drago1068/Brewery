"""Imports all model modules for SQLAlchemy/Alembic metadata discovery."""

from brewing_api.domain.audit.models import AuditEvent, BrewJournalEvent
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage, BrewTimer
from brewing_api.domain.identity.models import AuthSession, User
from brewing_api.domain.measurements.models import Deviation, Measurement
from brewing_api.domain.notifications.models import Notification
from brewing_api.domain.recipes.models import Recipe, RecipeVersion

__all__ = [
    "AuditEvent",
    "AuthSession",
    "BrewJournalEvent",
    "BrewSession",
    "BrewStage",
    "BrewTimer",
    "Deviation",
    "Measurement",
    "Notification",
    "Recipe",
    "RecipeVersion",
    "User",
]
