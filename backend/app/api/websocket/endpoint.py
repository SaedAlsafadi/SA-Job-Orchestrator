"""WebSocket endpoint for real-time client communication (ticket-authenticated)."""

import asyncio
import contextlib
from urllib.parse import urlsplit

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.websocket.events import manager
from app.api.websocket.subscriber import forward_user_events
from app.config.settings import get_settings
from app.core.exceptions import AuthError
from app.core.security import decode_token
from app.db.redis import get_redis
from app.db.session import async_session_factory
from app.models.user import User

logger = structlog.get_logger(__name__)
router = APIRouter()


def _origin_allowed(origin: str, allowed: list[str]) -> bool:
    """Allow exact origins and equivalent localhost/127.0.0.1 dev origins."""
    if not origin or origin in allowed:
        return True
    parsed = urlsplit(origin)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return False
    for configured in allowed:
        candidate = urlsplit(configured)
        if (
            candidate.hostname in {"localhost", "127.0.0.1", "::1"}
            and candidate.scheme == parsed.scheme
            and candidate.port == parsed.port
        ):
            return True
    return False


async def _active_user_exists(user_id: str) -> bool:
    """Reject stale/forged tenant subjects before accepting the socket."""
    async with async_session_factory() as db:
        user = await db.get(User, user_id)
        return bool(user and user.is_active and user.deleted_at is None)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Main WebSocket endpoint for real-time updates.

    Authenticated with a short-lived ticket (``?ticket=``) validated before ``accept()``.
    While connected, a background task subscribes to the user's Redis channel and forwards
    worker-published progress events to this socket (the cross-process bridge).
    """
    # Origin check (defense-in-depth).
    origin = ws.headers.get("origin", "")
    allowed = get_settings().cors_origins
    if not _origin_allowed(origin, allowed):
        await ws.close(code=4003, reason="Origin not allowed")
        return

    # Ticket authentication before accepting the connection.
    ticket = ws.query_params.get("ticket", "")
    try:
        payload = decode_token(ticket, expected_type="ws_ticket")
    except AuthError:
        await ws.close(code=4401, reason="Invalid or missing ticket")
        return
    user_id = payload.get("sub", "")
    if not user_id or not await _active_user_exists(user_id):
        await ws.close(code=4403, reason="Unknown or inactive tenant")
        return
    await manager.connect(ws, user_id)

    # Forward this user's published progress events to the socket (if Redis is available).
    redis = get_redis()
    sub_task: asyncio.Task | None = None
    if redis is not None:
        sub_task = asyncio.create_task(forward_user_events(redis, user_id, ws))

    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await manager.send_to(ws, {"type": "pong", "payload": {}})
            else:
                logger.debug("ws_message_received", user_id=user_id, data=data[:100])
    except WebSocketDisconnect:
        pass
    finally:
        if sub_task is not None:
            sub_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sub_task
        await manager.disconnect(ws, user_id)
