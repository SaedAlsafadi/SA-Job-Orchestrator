"""Per-connection Redis pub/sub subscriber.

Forwards a single user's published progress events (from the worker, via
``bus.publish_progress``) to one connected WebSocket. Started as a background task when
the socket connects and cancelled on disconnect.
"""

from __future__ import annotations

import asyncio

import structlog
from fastapi import WebSocket
from redis.asyncio import Redis

from app.api.websocket.bus import user_channel

logger = structlog.get_logger(__name__)


async def forward_user_events(redis: Redis, user_id: str, ws: WebSocket) -> None:
    """Subscribe to the user's channel and forward each event to ``ws`` until cancelled."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(user_channel(user_id))
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message["data"]
            text = data.decode() if isinstance(data, bytes) else data
            await ws.send_text(text)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("ws_subscriber_error", user_id=user_id, error=str(exc))
    finally:
        await pubsub.unsubscribe(user_channel(user_id))
        await pubsub.aclose()
