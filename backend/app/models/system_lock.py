"""System locking models."""

from datetime import datetime
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SystemLock(Base):
    """DB-backed distributed lock."""

    __tablename__ = "system_locks"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<SystemLock(key='{self.key}', expires_at={self.expires_at})>"
