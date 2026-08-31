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

@router.post("/link/token", response_model=LinkTokenResponse)
async def generate_link_token(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db)
):
    """Generate a one-time secure token for Telegram linking."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    token = TelegramLinkToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=15)
    )
    db.add(token)
    await db.commit()
    
    app = get_telegram_app()
    error_msg = app.bot_data.get("startup_error") if app else "Bot app not initialized"
    bot_username = app.bot_data.get("username") if app else None
    
    if not bot_username:
        # Fallback but we will append the error to the url for debugging
        import urllib.parse
        encoded_err = urllib.parse.quote(str(error_msg))
        bot_username = f"autoapply_bot?start={raw_token}&error={encoded_err}"
    else:
        bot_username = f"{bot_username}?start={raw_token}"
    
    return LinkTokenResponse(
        token=raw_token,
        bot_url=f"https://t.me/{bot_username}"
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
    
    if not conn:
        return TelegramStatusResponse(status="NOT CONNECTED")
        
    return TelegramStatusResponse(
        status="CONNECTED",
        username=conn.username,
        linked_at=conn.created_at
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
        user_id='test_user_id',
        text="👋 This is a test notification from AutoApply!"
    )
    return {"status": "ok"}
