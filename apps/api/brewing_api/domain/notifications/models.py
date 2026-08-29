import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base


class Notification(UuidTimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("brew_stage_id", "notification_type"),
        UniqueConstraint("id", "brew_session_id", name="uq_notification_session"),
        ForeignKeyConstraint(
            ["brew_stage_id", "brew_session_id"],
            ["brew_stages.id", "brew_stages.brew_session_id"],
            name="fk_notification_stage_session",
        ),
    )

    brew_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    brew_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    notification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="DUE", nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    requirement_template_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    satisfaction_source_type: Mapped[str | None] = mapped_column(String(40))
    satisfaction_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    resolution_source_type: Mapped[str | None] = mapped_column(String(40))
    resolution_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    priority: Mapped[str] = mapped_column(String(24), default="REQUIRED", nullable=False)
    schema_version: Mapped[str | None] = mapped_column(String(64))
    skip_reason: Mapped[str | None] = mapped_column(Text)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
