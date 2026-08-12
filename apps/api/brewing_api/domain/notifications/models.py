import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from brewing_api.domain.common import UuidTimestampMixin
from brewing_api.platform.database import Base


class Notification(UuidTimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("brew_stage_id", "notification_type"),)

    brew_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("brew_stages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    notification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="DUE", nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

