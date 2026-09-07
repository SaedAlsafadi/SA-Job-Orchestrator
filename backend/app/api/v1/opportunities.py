"""Opportunities ingestion API."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, UTC

from app.api.deps import get_current_user, get_tenant_db
from app.models.user import User
from app.models.job import Job
from app.core.job_discovery.manual_provider import ManualProvider
from app.services.application_route_resolver import ApplicationRouteResolver
from app.services.monitoring.utils import compute_content_hash

router = APIRouter(tags=["opportunities"])

class IngestOpportunityRequest(BaseModel):
    text: str
    source_type: str
    source_reference: Optional[str] = None
    title_override: Optional[str] = None
    company_override: Optional[str] = None


from arq.connections import ArqRedis
from app.db.arq import get_arq_pool
from app.models.enums import JobStatus
import hashlib

@router.post("/ingest")
async def ingest_opportunity(
    req: IngestOpportunityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
    pool: ArqRedis | None = Depends(get_arq_pool)
):
    # Determine the text to hash (URL or Paste)
    content_hash = hashlib.sha256(req.text.encode()).hexdigest()
    
    # Check deduplication first based on raw content
    existing_job = await db.execute(select(Job).where(Job.platform_job_id == content_hash))
    existing_job = existing_job.scalar_one_or_none()
    
    if existing_job:
        # Just return the existing job. In the future, we could append source provenance instead.
        return {"job_id": existing_job.id, "status": existing_job.status}
    
    # 1. Create Canonical Job in RECEIVED state
    job = Job(
        user_id=user.id,
        platform="manual",
        platform_job_id=content_hash,
        title="Processing...",
        company="Processing...",
        url=req.text if req.source_type == "url" else "",
        # Provenance
        source_type=req.source_type,
        source_reference=req.source_reference,
        raw_text=req.text,
        received_at=datetime.now(UTC),
        first_seen_at=datetime.now(UTC),
        content_hash=content_hash,
        status=JobStatus.RECEIVED
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # 2. Update to processing and enqueue
    job.status = JobStatus.PROCESSING
    await db.commit()
    
    if pool:
        await pool.enqueue_job("process_opportunity", job.id)
    
    return {"job_id": job.id, "status": job.status}

class RouteOverrideRequest(BaseModel):
    preferred_route_type: str

@router.post("/{job_id}/route")
async def override_application_route(
    job_id: str,
    req: RouteOverrideRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db)
):
    from app.models.application_route import ApplicationRoute
    
    job = (await db.execute(select(Job).where(Job.id == job_id, Job.user_id == user.id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    routes = (await db.execute(select(ApplicationRoute).where(ApplicationRoute.job_id == job_id))).scalars().all()
    
    found = False
    for route in routes:
        if route.route_type == req.preferred_route_type:
            route.is_preferred = True
            route.user_overridden = True
            route.overridden_by_id = user.id
            route.overridden_at = datetime.now(UTC)
            found = True
        else:
            route.is_preferred = False
            
    if not found:
        # Create a new manual route if one doesn't exist
        new_route = ApplicationRoute(
            job_id=job_id,
            route_type=req.preferred_route_type,
            confidence=1.0,
            is_preferred=True,
            user_overridden=True,
            overridden_by_id=user.id,
            overridden_at=datetime.now(UTC),
            resolved_at=datetime.now(UTC)
        )
        db.add(new_route)
        
    await db.commit()
    return {"status": "ok"}

