import uuid

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base


class BrewJournalEvent(UuidTimestampMixin, Base):
    __tablename__ = "brew_journal_events"

    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    brew_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AuditEvent(UuidTimestampMixin, Base):
    __tablename__ = "audit_events"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
