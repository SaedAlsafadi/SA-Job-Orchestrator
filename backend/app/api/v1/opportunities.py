"""Opportunities ingestion API."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_tenant_db
from app.models.job import Job
from app.models.user import User

router = APIRouter(tags=["opportunities"])


class IngestOpportunityRequest(BaseModel):
    text: str
    source_type: str
    source_reference: str | None = None
    title_override: str | None = None
    company_override: str | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if not self.text.strip():
            raise ValueError("Opportunity text cannot be empty.")
        if self.source_type == "url":
            from urllib.parse import urlparse

            parsed = urlparse(self.text.strip())
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Enter a valid public HTTP(S) job URL.")
        return self


import hashlib
from datetime import timedelta

from arq.connections import ArqRedis

from app.db.arq import get_arq_pool
from app.models.enums import JobStatus

# A job left in PROCESSING longer than the arq job_timeout (600s) + margin can
# never still be genuinely in flight - the queue lost it (e.g. it was enqueued
# to a Redis that went away, or the worker never ran). Re-ingest then retries.
_STALE_PROCESSING = timedelta(seconds=900)

_QUEUE_UNAVAILABLE_ERROR = (
    "Task queue unavailable - Redis is not running. Start Redis and the arq "
    "worker (arq app.workers.tasks.WorkerSettings), then re-submit the URL."
)


def _is_stale_processing(job):
    # True if a PROCESSING/RECEIVED row is older than any legitimate in-flight task.
    if job.status not in (JobStatus.PROCESSING, JobStatus.RECEIVED):
        return False
    updated = job.updated_at or job.received_at
    if updated is None:
        return True
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return datetime.now(UTC) - updated > _STALE_PROCESSING


@router.post("/ingest")
async def ingest_opportunity(
    req: IngestOpportunityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
    pool: ArqRedis | None = Depends(get_arq_pool),
):
    # Determine the text to hash (URL or Paste)
    content_hash = hashlib.sha256(req.text.encode()).hexdigest()

    # Deduplicate on the stable user-supplied source. ``platform_job_id`` is
    # replaced with a normalized content hash by the worker, so it cannot be
    # the retry key after the first successful extraction. Scope explicitly to
    # the current tenant and prefer the original row if legacy retries created
    # duplicates.
    existing_job = await db.execute(
        select(Job)
        .where(
            Job.user_id == user.id,
            Job.source_type == req.source_type,
            Job.raw_text == req.text,
        )
        .order_by(Job.created_at.asc())
        .limit(1)
    )
    existing_job = existing_job.scalar_one_or_none()

    job = None
    if existing_job:
        if existing_job.status == JobStatus.FAILED or _is_stale_processing(
            existing_job
        ):
            # Retry semantics: a FAILED row (or a stale in-flight one the queue
            # lost) is re-processed instead of returned - a transient
            # infrastructure failure must not permanently block a URL.
            existing_job.raw_data = {}
            job = existing_job
        else:
            # Just return the existing job. In the future, we could append source provenance instead.
            return {"job_id": existing_job.id, "status": existing_job.status}

    if job is None:
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
            status=JobStatus.RECEIVED,
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)

    # 2. Update to processing and enqueue
    job.status = JobStatus.PROCESSING
    await db.commit()

    if pool:
        await pool.enqueue_job("process_opportunity", job.id)
    else:
        # No queue behind the app: the job can never be processed. Fail it
        # loudly (the UI renders raw_data.error on the failed state) instead of
        # silently leaving the row in PROCESSING with the frontend polling forever.
        job.status = JobStatus.FAILED
        job.raw_data = {"error": _QUEUE_UNAVAILABLE_ERROR}
        await db.commit()

    return {"job_id": job.id, "status": job.status}


class RouteOverrideRequest(BaseModel):
    preferred_route_type: str


@router.post("/{job_id}/route")
async def override_application_route(
    job_id: str,
    req: RouteOverrideRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    from app.models.application_route import ApplicationRoute

    job = (
        await db.execute(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    routes = (
        (
            await db.execute(
                select(ApplicationRoute).where(ApplicationRoute.job_id == job_id)
            )
        )
        .scalars()
        .all()
    )

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
            user_id=user.id,
            job_id=job_id,
            route_type=req.preferred_route_type,
            confidence=1.0,
            is_preferred=True,
            user_overridden=True,
            overridden_by_id=user.id,
            overridden_at=datetime.now(UTC),
            resolved_at=datetime.now(UTC),
        )
        db.add(new_route)

    await db.commit()
    return {"status": "ok"}
