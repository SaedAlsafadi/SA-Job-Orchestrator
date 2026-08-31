"""Telegram Bot lifecycle and encapsulation."""

import asyncio
import structlog
from typing import Optional
from telegram.ext import Application, ApplicationBuilder

from app.config.settings import get_settings

logger = structlog.get_logger(__name__)

# Global bot instance
_telegram_app: Optional[Application] = None


async def start_telegram_bot() -> None:
    """Initialize and start the Telegram bot if enabled."""
    global _telegram_app
    settings = get_settings()

    if not settings.telegram_enabled or not settings.telegram_bot_token:
        logger.info("telegram_bot.disabled")
        return

    try:
        # Import handlers here to avoid circular imports during startup
        from app.services.telegram.handlers import register_handlers

        token = settings.telegram_bot_token.get_secret_value()
        if not token:
            logger.warning("telegram_bot.missing_token")
            return

        builder = ApplicationBuilder().token(token)
        if settings.telegram_proxy:
            builder = builder.proxy(settings.telegram_proxy).get_updates_proxy(settings.telegram_proxy)
            
        _telegram_app = builder.build()
        register_handlers(_telegram_app)

        await _telegram_app.initialize()

        # Fetch bot info dynamically as per Phase 11 requirements
        bot_info = await _telegram_app.bot.get_me()
        _telegram_app.bot_data["username"] = bot_info.username
        logger.info("telegram_bot.started", username=bot_info.username)

        if settings.telegram_polling:
            await _telegram_app.start()
            await _telegram_app.updater.start_polling()
            logger.info("telegram_bot.polling_started")

    except Exception as exc:
        logger.error("telegram_bot.startup_failed", error=str(exc))
        if _telegram_app:
            _telegram_app.bot_data["startup_error"] = str(exc)


async def stop_telegram_bot() -> None:
    """Stop the Telegram bot."""
    global _telegram_app
    if _telegram_app:
        try:
            if _telegram_app.updater and _telegram_app.updater.running:
                await _telegram_app.updater.stop()
            await _telegram_app.stop()
            await _telegram_app.shutdown()
            logger.info("telegram_bot.stopped")
        except Exception as exc:
            logger.error("telegram_bot.shutdown_error", error=str(exc))
        finally:
            _telegram_app = None


def get_telegram_app() -> Optional[Application]:
    """Get the running telegram application."""
    return _telegram_app
