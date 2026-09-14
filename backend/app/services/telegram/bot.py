"""Telegram Bot lifecycle and encapsulation."""

import structlog
from telegram.ext import Application, ApplicationBuilder

from app.config.settings import get_settings

logger = structlog.get_logger(__name__)

# Global bot instance
_telegram_app: Application | None = None
_runtime_username: str | None = None
_startup_error: str | None = None


class TelegramConfigurationError(RuntimeError):
    """Safe, public configuration failure with no credential material."""


def _safe_startup_error(exc: Exception) -> str:
    """Map provider exceptions to actionable text without logging the token."""
    if isinstance(exc, TelegramConfigurationError):
        return str(exc)
    if type(exc).__name__ == "InvalidToken":
        return "Telegram rejected TELEGRAM_BOT_TOKEN. Verify the token in BotFather."
    return "Telegram bot startup failed. Verify the bot configuration and network access."


async def start_telegram_bot() -> None:
    """Initialize and start the Telegram bot if enabled."""
    global _telegram_app, _runtime_username, _startup_error
    settings = get_settings()
    _runtime_username = None
    _startup_error = None

    if not settings.telegram_enabled:
        logger.info("telegram_bot.disabled")
        return

    token = settings.telegram_bot_token.get_secret_value() if settings.telegram_bot_token else ""
    configured_username = (settings.telegram_bot_username or "").lstrip("@").strip()
    missing = [
        name
        for name, value in {
            "TELEGRAM_BOT_TOKEN": token,
            "TELEGRAM_BOT_USERNAME": configured_username,
        }.items()
        if not value
    ]
    if missing:
        logger.warning("telegram_bot.not_configured", missing=missing)
        return
    if not settings.telegram_polling:
        _startup_error = (
            "Telegram webhook mode is not configured. Set TELEGRAM_POLLING=true "
            "or configure a supported webhook deployment."
        )
        logger.error("telegram_bot.startup_failed", error_code=_startup_error)
        return

    try:
        # Import handlers here to avoid circular imports during startup
        from app.services.telegram.handlers import register_handlers

        builder = ApplicationBuilder().token(token)
        if settings.telegram_proxy:
            builder = builder.proxy(settings.telegram_proxy).get_updates_proxy(
                settings.telegram_proxy
            )

        _telegram_app = builder.build()
        register_handlers(_telegram_app)

        await _telegram_app.initialize()

        # Fetch bot info dynamically as per Phase 11 requirements
        bot_info = await _telegram_app.bot.get_me()
        _runtime_username = bot_info.username
        _telegram_app.bot_data["username"] = _runtime_username
        if configured_username.casefold() != (_runtime_username or "").casefold():
            raise TelegramConfigurationError(
                "TELEGRAM_BOT_USERNAME does not match the bot authenticated by TELEGRAM_BOT_TOKEN."
            )
        logger.info("telegram_bot.started", username=_runtime_username)

        if settings.telegram_polling:
            await _telegram_app.start()
            await _telegram_app.updater.start_polling()
            logger.info("telegram_bot.polling_started")

    except Exception as exc:
        _startup_error = _safe_startup_error(exc)
        logger.error(
            "telegram_bot.startup_failed",
            error_code=_startup_error,
            exception_type=type(exc).__name__,
        )
        if _telegram_app:
            _telegram_app.bot_data["startup_error"] = _startup_error


async def stop_telegram_bot() -> None:
    """Stop the Telegram bot."""
    global _telegram_app, _runtime_username, _startup_error
    if _telegram_app:
        try:
            if _telegram_app.updater and _telegram_app.updater.running:
                await _telegram_app.updater.stop()
            await _telegram_app.stop()
            await _telegram_app.shutdown()
            logger.info("telegram_bot.stopped")
        except Exception as exc:
            # Provider exception text can contain request URLs (and therefore the bot
            # token). Record only the exception class at this trust boundary.
            logger.error("telegram_bot.shutdown_error", exception_type=type(exc).__name__)
        finally:
            _telegram_app = None
            _runtime_username = None
            _startup_error = None


def get_telegram_app() -> Application | None:
    """Get the running telegram application."""
    return _telegram_app if not _startup_error else None


def get_telegram_runtime_state() -> dict[str, str | bool | None]:
    """Return safe public runtime state; the token is never included."""
    settings = get_settings()
    token_present = bool(
        settings.telegram_bot_token
        and settings.telegram_bot_token.get_secret_value()
    )
    configured_username = (settings.telegram_bot_username or "").lstrip("@").strip() or None
    configured = bool(settings.telegram_enabled and token_present and configured_username)
    running = bool(_telegram_app and _runtime_username and not _startup_error)
    return {
        "bot_username": _runtime_username or configured_username,
        "bot_configured": configured,
        "bot_running": running,
        "update_mode": "polling" if settings.telegram_polling else "webhook",
        "configuration_error": _startup_error if configured else None,
    }
