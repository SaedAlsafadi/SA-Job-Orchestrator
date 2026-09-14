"""Telegram configuration and credential-safe failure behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.telegram import bot


def _settings(*, token="123456:secret", username="MyCareerBot", enabled=True, polling=True):
    return SimpleNamespace(
        telegram_enabled=enabled,
        telegram_polling=polling,
        telegram_bot_token=SimpleNamespace(get_secret_value=lambda: token) if token is not None else None,
        telegram_bot_username=username,
        telegram_proxy=None,
    )


@pytest.fixture(autouse=True)
def _clear_runtime(monkeypatch):
    monkeypatch.setattr(bot, "_telegram_app", None)
    monkeypatch.setattr(bot, "_runtime_username", None)
    monkeypatch.setattr(bot, "_startup_error", None)


@pytest.mark.asyncio
async def test_missing_username_is_not_configured(monkeypatch):
    monkeypatch.setattr(bot, "get_settings", lambda: _settings(username=None))
    builder = MagicMock()
    monkeypatch.setattr(bot, "ApplicationBuilder", builder)

    await bot.start_telegram_bot()

    assert builder.called is False
    state = bot.get_telegram_runtime_state()
    assert state["bot_configured"] is False
    assert state["bot_running"] is False
    assert state["configuration_error"] is None


@pytest.mark.asyncio
async def test_invalid_token_failure_is_actionable_and_never_echoes_token(monkeypatch):
    secret = "123456:must-not-leak"
    monkeypatch.setattr(bot, "get_settings", lambda: _settings(token=secret))

    class InvalidToken(Exception):  # noqa: N818 - mirrors telegram.error.InvalidToken
        pass

    app = SimpleNamespace(
        bot=SimpleNamespace(get_me=AsyncMock()),
        bot_data={},
        add_handler=MagicMock(),
        initialize=AsyncMock(side_effect=InvalidToken(f"rejected {secret}")),
    )
    builder = MagicMock()
    builder.return_value.token.return_value.build.return_value = app
    monkeypatch.setattr(bot, "ApplicationBuilder", builder)

    await bot.start_telegram_bot()

    state = bot.get_telegram_runtime_state()
    assert state["bot_configured"] is True
    assert state["bot_running"] is False
    assert "TELEGRAM_BOT_TOKEN" in str(state["configuration_error"])
    assert "BotFather" in str(state["configuration_error"])
    assert secret not in str(state)


@pytest.mark.asyncio
async def test_configured_username_must_match_get_me(monkeypatch):
    monkeypatch.setattr(bot, "get_settings", lambda: _settings(username="ExpectedBot"))
    app = SimpleNamespace(
        bot=SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username="DifferentBot"))),
        bot_data={},
        add_handler=MagicMock(),
        initialize=AsyncMock(),
    )
    builder = MagicMock()
    builder.return_value.token.return_value.build.return_value = app
    monkeypatch.setattr(bot, "ApplicationBuilder", builder)

    await bot.start_telegram_bot()

    state = bot.get_telegram_runtime_state()
    assert state["bot_username"] == "DifferentBot"
    assert state["bot_running"] is False
    assert "does not match" in str(state["configuration_error"])
    assert bot.get_telegram_app() is None


@pytest.mark.asyncio
async def test_polling_bot_is_running_only_after_verified_get_me(monkeypatch):
    monkeypatch.setattr(bot, "get_settings", lambda: _settings())
    updater = SimpleNamespace(start_polling=AsyncMock(), running=False)
    app = SimpleNamespace(
        bot=SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username="MyCareerBot"))),
        bot_data={},
        add_handler=MagicMock(),
        updater=updater,
        initialize=AsyncMock(),
        start=AsyncMock(),
    )
    builder = MagicMock()
    builder.return_value.token.return_value.build.return_value = app
    monkeypatch.setattr(bot, "ApplicationBuilder", builder)

    await bot.start_telegram_bot()

    state = bot.get_telegram_runtime_state()
    assert state == {
        "bot_username": "MyCareerBot",
        "bot_configured": True,
        "bot_running": True,
        "update_mode": "polling",
        "configuration_error": None,
    }
    app.start.assert_awaited_once()
    updater.start_polling.assert_awaited_once()


@pytest.mark.asyncio
async def test_unimplemented_webhook_mode_fails_visibly(monkeypatch):
    monkeypatch.setattr(bot, "get_settings", lambda: _settings(polling=False))

    await bot.start_telegram_bot()

    state = bot.get_telegram_runtime_state()
    assert state["bot_running"] is False
    assert "webhook mode is not configured" in str(state["configuration_error"])
