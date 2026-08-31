"""Telegram handlers for python-telegram-bot."""

import structlog
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from sqlalchemy import select, delete, update
from datetime import datetime, UTC

from app.db.session import async_session_factory
from app.models.telegram_connection import TelegramConnection, TelegramLinkToken, TelegramCallbackReference
from app.models.application import Application as JobApplication, ApplicationStatus
from app.services.telegram.intake import process_inbound_message

logger = structlog.get_logger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start and deep-linking."""
    if not update.message or not update.effective_chat:
        return

    args = context.args
    chat_id = update.effective_chat.id
    username = update.effective_chat.username

    if not args:
        await update.message.reply_text(
            "Welcome to AutoApply! Please generate a connection link from your Web Dashboard Settings to link your account."
        )
        return

    import hashlib
    raw_token = args[0]
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    async with async_session_factory() as db:
        # Check token
        token_record = (await db.execute(
            select(TelegramLinkToken).where(
                TelegramLinkToken.token_hash == token_hash,
                TelegramLinkToken.used == False,
                TelegramLinkToken.expires_at > datetime.now(UTC)
            )
        )).scalar_one_or_none()
        
        if not token_record:
            await update.message.reply_text("Invalid or expired linking token. Please generate a new one from your dashboard.")
            return
            
        user_id = token_record.user_id
        
        # Invalidate token
        token_record.used = True
        
        # Link connection
        existing = (await db.execute(select(TelegramConnection).where(TelegramConnection.user_id == user_id))).scalar_one_or_none()
        if existing:
            existing.chat_id = chat_id
            existing.username = username
            existing.is_active = True
        else:
            db.add(TelegramConnection(
                user_id=user_id,
                chat_id=chat_id,
                username=username,
                is_active=True
            ))
            
        await db.commit()
        
    await update.message.reply_text(
        "✅ Your Telegram account has been successfully linked!\n\n"
        "You will now receive notifications when job applications are ready for review. "
        "You can also forward job descriptions or links here to automatically add them to your queue."
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inbound job opportunities."""
    if not update.message or not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    text = update.message.text or update.message.caption or ""
    
    if not text.strip():
        return
        
    # Verify user is linked
    async with async_session_factory() as db:
        conn = (await db.execute(
            select(TelegramConnection).where(TelegramConnection.chat_id == chat_id, TelegramConnection.is_active == True)
        )).scalar_one_or_none()
        
        if not conn:
            await update.message.reply_text("Your account is not linked. Please link it via the Web Dashboard.")
            return
            
        user_id = conn.user_id
        
    # Send processing message
    status_msg = await update.message.reply_text("⏳ Processing job opportunity...")
    
    try:
        # Run inbound intake pipeline in background or inline
        await process_inbound_message(user_id, text, update.message.message_id)
        # We don't delete status_msg yet, the notifier will send a new message.
    except Exception as exc:
        logger.error("telegram.intake_failed", error=str(exc))
        await status_msg.edit_text("❌ Failed to process this message. Ensure it contains a clear job description or URL.")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks (Approve, Reject)."""
    query = update.callback_query
    if not query or not update.effective_chat:
        return
        
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    
    if not data or not data.startswith("cb:"):
        return
        
    _, action, ref_id = data.split(":", 2)
    
    async with async_session_factory() as db:
        # Verify user
        conn = (await db.execute(
            select(TelegramConnection).where(TelegramConnection.chat_id == chat_id, TelegramConnection.is_active == True)
        )).scalar_one_or_none()
        if not conn:
            await query.edit_message_text("Your account is not linked.")
            return
            
        # Get callback reference
        ref = (await db.execute(
            select(TelegramCallbackReference).where(TelegramCallbackReference.id == ref_id)
        )).scalar_one_or_none()
        
        if not ref or ref.expires_at < datetime.now(UTC) or ref.user_id != conn.user_id or ref.action != action:
            await query.edit_message_text("This action has expired or is invalid.")
            return
            
        app = (await db.execute(select(JobApplication).where(JobApplication.id == ref.application_id))).scalar_one_or_none()
        if not app:
            await query.edit_message_text("Application not found.")
            return
            
        if action == "approve":
            from app.services.submission import SubmissionService
            if app.status != ApplicationStatus.WAITING_FOR_REVIEW:
                await query.edit_message_text("Application is no longer waiting for review.")
                return
                
            try:
                # Approve
                submission_service = SubmissionService(db)
                await submission_service.approve_application(app.id, conn.user_id)
                await query.edit_message_text("✅ Application approved and queued for submission!")
            except Exception as exc:
                logger.error("telegram.approve_failed", error=str(exc))
                await query.edit_message_text(f"❌ Could not approve application: {str(exc)}")
                
        elif action == "reject":
            if app.status != ApplicationStatus.WAITING_FOR_REVIEW:
                await query.edit_message_text("Application is no longer waiting for review.")
                return
            app.status = ApplicationStatus.REJECTED
            await db.commit()
            await query.edit_message_text("❌ Application rejected.")


def register_handlers(app: Application) -> None:
    """Register all Telegram handlers on the application."""
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

