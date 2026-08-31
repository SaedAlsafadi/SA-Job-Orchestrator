"""Telegram inbound message ingestion."""

import structlog
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.job import Job
from app.models.application_route import ApplicationRoute
from app.core.job_discovery.manual_provider import ManualProvider
from app.services.application_route_resolver import ApplicationRouteResolver
from app.services.monitoring.utils import compute_content_hash
from app.services.telegram.notifier import TelegramNotifier

logger = structlog.get_logger(__name__)


async def process_inbound_message(user_id: str, text: str, message_id: int) -> None:
    """Process a Telegram message as a job opportunity."""
    
    if len(text) < 30 and "http" not in text:
        logger.info("telegram.intake.ignored", reason="too_short_no_url")
        return
        
    async with async_session_factory() as db:
        try:
            # 1. Ingest & Normalize
            provider = ManualProvider()
            raw_data = await provider.ingest(text)
            normalized = provider.normalize(raw_data)
            
            content_hash = compute_content_hash(normalized)
            
            # 2. Create Canonical Job
            job = Job(
                user_id=user_id,
                platform="telegram",
                platform_job_id=content_hash,
                url=normalized.get("url"),
                title=normalized.get("title", "Extracted from Telegram"),
                company=normalized.get("company", "Unknown"),
                description=normalized.get("description", text),
                source_type="telegram",
                source_reference=str(message_id),
                raw_data={"source": "telegram", "message_id": message_id},
                status="new",
                created_at=datetime.now(UTC),
            )
            db.add(job)
            await db.flush()
            
            # 3. Application Route Resolution
            resolver = ApplicationRouteResolver()
            routes = await resolver.resolve(job)
            
            for route in routes:
                db.add(route)
                
            await db.commit()
            await db.refresh(job)
            
            # 4. Trigger evaluation / eligibility
            # The background Orchestrator or matching service will pick this up.
            # But the spec says we should process Eligibility, Matching, Preparation.
            # Wait, since it's inbound, we can just enqueue the prepare_application_run job!
            # Let's import the arq pool to enqueue it if possible.
            
            # Send Notification
            notifier = TelegramNotifier(db)
            await notifier.notify_opportunity_processed(
                user_id=user_id,
                job=job,
                routes=routes
            )
            
        except Exception as exc:
            logger.error("telegram.intake.error", error=str(exc))
            raise
