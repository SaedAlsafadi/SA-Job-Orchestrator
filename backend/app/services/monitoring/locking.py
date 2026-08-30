"""Distributed locking mechanism for monitoring cycles."""

import asyncio
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import structlog
from contextlib import asynccontextmanager

from app.config.settings import get_settings
from app.models.monitoring import MonitoringSchedule

logger = structlog.get_logger(__name__)

class MonitoringLockError(Exception):
    pass

@asynccontextmanager
async def acquire_monitoring_lock(db: AsyncSession, platform: str, source: str):
    """
    Acquire a lock for the given platform and source.
    If Redis is available, use Redis lock.
    If not, use a poor-man's DB lock via an active schedule record.
    """
    settings = get_settings()
    has_redis = bool(settings.redis_url)
    
    lock_key = f"monitor_lock:{platform}:{source}"
    
    if has_redis:
        try:
            from redis.asyncio import Redis
            import redis.exceptions
            redis_client = Redis.from_url(settings.redis_url)
            
            # Simple SET NX PX lock
            acquired = await redis_client.set(lock_key, "locked", nx=True, px=600000) # 10 min
            if not acquired:
                raise MonitoringLockError(f"Could not acquire Redis lock for {lock_key}")
            
            try:
                yield
            finally:
                await redis_client.delete(lock_key)
                await redis_client.aclose()
        except ImportError:
            # redis not installed, fallback to DB
            logger.warning("Redis package not installed, falling back to DB lock")
            has_redis = False
        except Exception as e:
            if isinstance(e, MonitoringLockError):
                raise
            logger.warning(f"Redis error: {e}, falling back to DB lock")
            has_redis = False

    if not has_redis:
        # DB-backed fallback lock
        from app.models.system_lock import SystemLock
        from sqlalchemy.exc import IntegrityError
        from datetime import timedelta
        
        expires = datetime.now(UTC) + timedelta(minutes=10)
        
        lock_rec = SystemLock(key=lock_key, expires_at=expires)
        db.add(lock_rec)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            # Lock exists, check if expired
            stmt = select(SystemLock).where(SystemLock.key == lock_key)
            existing_lock = (await db.execute(stmt)).scalar_one_or_none()
            if existing_lock and existing_lock.expires_at > datetime.now(UTC):
                raise MonitoringLockError(f"Could not acquire DB lock for {lock_key}")
            elif existing_lock:
                # Expired, update it
                existing_lock.expires_at = expires
                await db.commit()
            else:
                raise MonitoringLockError(f"Could not acquire DB lock for {lock_key} (race condition)")
        
        try:
            yield
        finally:
            stmt = select(SystemLock).where(SystemLock.key == lock_key)
            existing_lock = (await db.execute(stmt)).scalar_one_or_none()
            if existing_lock:
                await db.delete(existing_lock)
                await db.commit()
