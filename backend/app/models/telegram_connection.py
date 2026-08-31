"""Telegram integration models."""

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TelegramConnection(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Binds a platform user to a Telegram chat."""

    __tablename__ = "telegram_connections"

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    chat_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TelegramLinkToken(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Temporary token for linking accounts."""

    __tablename__ = "telegram_link_tokens"

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class TelegramCallbackReference(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Opaque reference for Telegram inline button callbacks."""

    __tablename__ = "telegram_callback_references"

    # We use the UUIDPrimaryKeyMixin, so id is a 32-char hex string.
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    application_id: Mapped[str] = mapped_column(String(32), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)

class NotificationLog(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Logs sent notifications to prevent duplicates."""

    __tablename__ = "notification_logs"
    __table_args__ = (
        Index("ix_notification_logs_app_type", "application_id", "notification_type", unique=True),
    )

    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    application_id: Mapped[str] = mapped_column(String(32), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(32), default="sent", nullable=False)

