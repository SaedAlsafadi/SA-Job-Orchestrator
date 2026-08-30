"""Opportunities ingestion API."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
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


@router.post("/ingest")
async def ingest_opportunity(
    req: IngestOpportunityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db)
):
    # 1. Ingest & Normalize
    provider = ManualProvider()
    raw_data = await provider.ingest(
        req.text, 
        title_override=req.title_override, 
        company_override=req.company_override
    )
    normalized = provider.normalize(raw_data)
    
    content_hash = compute_content_hash(normalized)
    
    # 2. Create Canonical Job
    job = Job(
        user_id=user.id,
        platform=normalized.get("platform", "manual"), # Keeping legacy field intact but fallback
        platform_job_id=content_hash, # Using hash as ID for manual inputs
        title=normalized["title"],
        company=normalized["company"],
        description=normalized["description"],
        location=normalized["location"],
        url=normalized["url"],
        application_url=normalized.get("application_url"),
        requirements=normalized.get("requirements"),
        salary_range=normalized.get("salary_range"),
        remote=normalized.get("remote", False),
        employment_type=normalized.get("employment_type"),
        
        # Provenance
        source_type=req.source_type,
        source_reference=req.source_reference,
        raw_text=req.text,
        raw_source_payload=raw_data,
        received_at=datetime.now(UTC),
        first_seen_at=datetime.now(UTC),
        content_hash=content_hash,
        status="new"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # 3. Application Route Resolution
    resolver = ApplicationRouteResolver()
    routes = await resolver.resolve(job)
    
    for route in routes:
        db.add(route)
        
    await db.commit()
    
    # In a real workflow, we would trigger Eligibility -> Match -> Rank -> Apply tasks here via Arq
    
    return {"job_id": job.id, "routes_resolved": len(routes)}
