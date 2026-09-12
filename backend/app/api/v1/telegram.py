"""Telegram integration API routes."""

import hashlib
import secrets
from datetime import datetime, timedelta, UTC
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import get_current_user, get_tenant_db
from app.models.user import User
from app.models.telegram_connection import TelegramConnection, TelegramLinkToken
from app.services.telegram.bot import get_telegram_app
from app.services.telegram.notifier import TelegramNotifier

router = APIRouter(tags=["telegram"])

class LinkTokenResponse(BaseModel):
    token: str
    bot_url: str

class TelegramStatusResponse(BaseModel):
    status: str
    username: str | None = None
    linked_at: datetime | None = None
    bot_username: str | None = None
    bot_configured: bool = False
    bot_running: bool = False
    update_mode: str | None = None


def _bot_runtime_status() -> dict:
    """Return public bot health without ever exposing the configured token."""
    from app.config.settings import get_settings

    settings = get_settings()
    app = get_telegram_app()
    runtime_username = app.bot_data.get("username") if app else None
    configured_username = (settings.telegram_bot_username or "").lstrip("@").strip() or None
    running = bool(app and runtime_username and not app.bot_data.get("startup_error"))
    return {
        "bot_username": runtime_username or configured_username,
        "bot_configured": bool(settings.telegram_enabled and settings.telegram_bot_token),
        "bot_running": running,
        "update_mode": "polling" if settings.telegram_polling else "webhook",
    }

@router.post("/link/token", response_model=LinkTokenResponse)
async def generate_link_token(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db)
):
    """Generate a one-time secure token for Telegram linking."""
    runtime = _bot_runtime_status()
    bot_username = runtime["bot_username"]
    if not runtime["bot_running"] or not bot_username:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is not configured and running.",
        )
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    token = TelegramLinkToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=15)
    )
    db.add(token)
    await db.commit()
    
    return LinkTokenResponse(
        token=raw_token,
        bot_url=f"https://t.me/{bot_username}?start={raw_token}"
    )

@router.get("/status", response_model=TelegramStatusResponse)
async def get_telegram_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db)
):
    """Check if the user is connected to Telegram."""
    conn = (await db.execute(
        select(TelegramConnection).where(
            TelegramConnection.user_id == user.id, 
            TelegramConnection.is_active == True
        )
    )).scalar_one_or_none()
    
    runtime = _bot_runtime_status()
    if not conn:
        return TelegramStatusResponse(status="NOT CONNECTED", **runtime)
        
    return TelegramStatusResponse(
        status="CONNECTED" if runtime["bot_running"] else "BOT UNAVAILABLE",
        username=conn.username,
        linked_at=conn.created_at,
        **runtime,
    )

@router.delete("/link")
async def disconnect_telegram(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db)
):
    """Disconnect Telegram."""
    conn = (await db.execute(
        select(TelegramConnection).where(
            TelegramConnection.user_id == user.id, 
            TelegramConnection.is_active == True
        )
    )).scalar_one_or_none()
    
    if conn:
        conn.is_active = False
        await db.commit()
        
    return {"status": "ok"}

@router.post("/test")
async def test_telegram_notification(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db)
):
    """Send a test notification."""
    notifier = TelegramNotifier(db)
    await notifier._send_message(
        user_id=user.id,
        text="👋 This is a test notification from your job application assistant."
    )
    return {"status": "ok"}
