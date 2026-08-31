"""Telegram notifications service."""

import structlog
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.models.telegram_connection import TelegramConnection, TelegramCallbackReference, NotificationLog
from app.models.application import Application as JobApplication
from app.models.job import Job
from app.services.telegram.bot import get_telegram_app
from app.config.settings import get_settings
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

logger = structlog.get_logger(__name__)


class TelegramNotifier:
    """Handles outbound Telegram notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def _send_message(
        self, 
        user_id: str, 
        text: str, 
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        notification_type: str = "GENERIC",
        application_id: Optional[str] = None
    ) -> None:
        """Send a message to a user via Telegram."""
        if not self.settings.telegram_enabled:
            return

        conn = (await self.db.execute(
            select(TelegramConnection).where(
                TelegramConnection.user_id == user_id, 
                TelegramConnection.is_active == True
            )
        )).scalar_one_or_none()

        if not conn:
            return

        # Deduplication
        if application_id:
            existing = (await self.db.execute(
                select(NotificationLog).where(
                    NotificationLog.application_id == application_id,
                    NotificationLog.notification_type == notification_type
                )
            )).scalar_one_or_none()
            
            if existing:
                logger.info("telegram.notifier.duplicate_skipped", app=application_id, type=notification_type)
                return

        app = get_telegram_app()
        if not app:
            logger.warning("telegram.notifier.app_not_running")
            return

        try:
            msg = await app.bot.send_message(
                chat_id=conn.chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
            if application_id:
                self.db.add(NotificationLog(
                    user_id=user_id,
                    application_id=application_id,
                    notification_type=notification_type,
                    telegram_message_id=msg.message_id
                ))
                await self.db.commit()
                
        except Exception as exc:
            logger.error("telegram.notifier.send_failed", error=str(exc))
            # Don't fail the business logic

    async def notify_application_ready(self, user_id: str, app: JobApplication, job: Job) -> None:
        """Send APPLICATION READY notification with Review/Approve/Reject buttons."""
        
        match_str = f"{int(job.match_score * 100)}%" if job.match_score else "N/A"
        
        text = (
            "🚀 *APPLICATION READY*\n\n"
            f"*{job.title}*\n"
            f"Company: {job.company}\n"
            f"Location: {job.location}\n"
            f"Platform: {job.platform}\n"
            f"Match: {match_str}\n\n"
            f"CV: Ready\n"
        )
        
        # Create callback references
        def create_ref(action: str) -> str:
            import uuid
            ref = TelegramCallbackReference(
                user_id=user_id,
                application_id=app.id,
                action=action,
                expires_at=datetime.now(UTC)
            )
            # Give it 7 days expiry
            # We must assign the ID here to use in callback data
            # UUIDPrimaryKeyMixin handles ID on flush, we can do it manually or flush
            return ref

        review_ref = TelegramCallbackReference(user_id=user_id, application_id=app.id, action="review", expires_at=datetime.now(UTC))
        approve_ref = TelegramCallbackReference(user_id=user_id, application_id=app.id, action="approve", expires_at=datetime.now(UTC))
        reject_ref = TelegramCallbackReference(user_id=user_id, application_id=app.id, action="reject", expires_at=datetime.now(UTC))
        
        self.db.add(review_ref)
        self.db.add(approve_ref)
        self.db.add(reject_ref)
        await self.db.flush() # To get IDs

        # Make expires_at a week from now
        from datetime import timedelta
        week_later = datetime.now(UTC) + timedelta(days=7)
        review_ref.expires_at = week_later
        approve_ref.expires_at = week_later
        reject_ref.expires_at = week_later
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 Review", url=f"{self.settings.frontend_url}/applications/{app.id}"),
                InlineKeyboardButton("✅ Approve", callback_data=f"cb:approve:{approve_ref.id}")
            ],
            [
                InlineKeyboardButton("❌ Reject", callback_data=f"cb:reject:{reject_ref.id}")
            ]
        ]
        
        await self.db.commit()

        await self._send_message(
            user_id=user_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            notification_type="APPLICATION_READY",
            application_id=app.id
        )

    async def notify_opportunity_processed(self, user_id: str, job: Job, routes: list) -> None:
        """Send OPPORTUNITY PROCESSED notification."""
        
        match_str = f"{int(job.match_score * 100)}%" if job.match_score else "Pending"
        route_str = routes[0].route_type if routes else "None"
        conf_str = f"{routes[0].confidence:.1f}" if routes and routes[0].confidence else "N/A"
        
        text = (
            "✨ *OPPORTUNITY PROCESSED*\n\n"
            f"*{job.title}*\n"
            f"Company: {job.company}\n"
            f"Location: {job.location}\n"
            f"Match: {match_str}\n"
            f"Application Route: {route_str}\n"
            f"Route confidence: {conf_str}\n"
            f"Application status: WAITING_FOR_REVIEW\n"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 Review", url=f"{self.settings.frontend_url}/jobs/{job.id}")
            ]
        ]
        
        await self._send_message(
            user_id=user_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            notification_type="OPPORTUNITY_PROCESSED",
            application_id=job.id
        )
