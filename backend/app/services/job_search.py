"""Job search and management service.

Handles job CRUD operations, search orchestration across platform
scrapers, and ATS-based job analysis.
"""

import hashlib
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.config.settings import get_settings
from app.core.automation.platforms import platform_registry
from app.core.automation.platforms.base import JobListing
from app.core.exceptions import RecordNotFoundError
from app.core.job_discovery.exa_search import ExaJobSearch
from app.models.job import Job
from app.models.resume import Resume
from app.models.candidate_profile import CandidateProfile
from app.schemas.candidate_profile import CandidateProfileSchema
from app.services.matching import CandidateJobMatcher
from app.core.llm.client import LLMClient
from app.core.llm.router import LLMTaskRouter
import asyncio
from app.observability.metrics import job_searches_total, jobs_found_total
from app.schemas.matching import CandidateMatchResult
from app.schemas.job import (
    
    JobListingResponse,
    JobListResponse,
    JobSearchRequest,
)

logger = structlog.get_logger(__name__)


def _job_identity(job: Job) -> str:
    """Stable, non-empty ``platform_job_id`` for a scraped listing.

    Browser-scraped listings often arrive with a blank id (the agent returned no ``id`` field);
    without a stable value distinct listings collide on the ``(user, platform, platform_job_id)``
    unique constraint AND collapse during dedup. Derive one from the URL (hashed, so it fits the
    column and is stable) when the id is blank.
    """
    pid = (job.platform_job_id or "").strip()
    if pid:
        return pid
    url = (job.url or "").strip()
    if url:
        return "url:" + hashlib.sha1(url.encode()).hexdigest()[:16]
    return ""


async def search_jobs(
    db: AsyncSession,
    request: JobSearchRequest,
    user_id: str,
) -> JobListResponse:
    """Search for jobs across configured platforms.

    Iterates over requested platforms, calls each platform's ``search``
    method, converts results to ``Job`` model instances, and persists
    them to the database. Partial failures are logged and skipped so
    that results from healthy platforms are still returned.

    Args:
        db: Async database session.
        request: Job search parameters.

    Returns:
        Paginated list of matching job listings.
    """
    logger.info(
        "job_search_requested",
        query=request.query,
        location=request.location,
        platforms=request.platforms,
        limit=request.limit,
    )

    platforms_to_search = request.platforms or platform_registry.list_platforms()

    if not platforms_to_search:
        logger.warning("job_search.no_platforms_available")
        return JobListResponse(
            items=[],
            total=0,
            page=1,
            page_size=request.limit,
            has_next=False,
        )

    all_jobs: list[Job] = []

    # Pre-fetch the user's existing jobs keyed by (platform, id) so dedup happens in memory. The
    # previous per-listing SELECT ran under autoflush, so distinct listings sharing an empty/dup
    # platform_job_id collapsed onto one row (silent data loss) — this also removes that N+1.
    existing_by_key: dict[tuple[str, str], Job] = {
        (j.platform, j.platform_job_id): j
        for j in (
            await db.execute(select(Job).where(Job.user_id == user_id))
        ).scalars().all()
    }
    seen: set[tuple[str, str]] = set()

    def _register(job: Job) -> None:
        """Add a new job or fold it onto an already-known one; never append a duplicate."""
        ident = _job_identity(job)
        if not ident:  # no id and no url — can't key it; keep as-is (degenerate data)
            db.add(job)
            all_jobs.append(job)
            return
        # Persist the derived id so distinct blank-id listings don't collide on the unique index.
        job.platform_job_id = ident
        key = (job.platform, ident)
        if key in seen:
            return
        seen.add(key)
        existing = existing_by_key.get(key)
        if existing is not None:
            all_jobs.append(existing)
        else:
            db.add(job)
            existing_by_key[key] = job
            all_jobs.append(job)

    for platform_name in platforms_to_search:
        if not platform_registry.has(platform_name):
            logger.warning(
                "job_search.platform_not_registered",
                platform=platform_name,
            )
            continue

        try:
            platform = platform_registry.create(platform_name)
            listings: list[JobListing] = await platform.search(
                query=request.query,
                location=request.location,
                filters=request.filters or None,
            )
            logger.info(
                "job_search.platform_results",
                platform=platform_name,
                count=len(listings),
            )
            job_searches_total.labels(platform=platform_name).inc()
            jobs_found_total.labels(platform=platform_name).inc(len(listings))
        except Exception as exc:
            logger.error(
                "job_search.platform_search_failed",
                platform=platform_name,
                error=str(exc),
            )
            continue

        for listing in listings:
            try:
                _register(_listing_to_job(listing, user_id))
            except Exception as exc:
                logger.warning(
                    "job_search.listing_conversion_failed",
                    platform=platform_name,
                    listing_id=listing.platform_job_id,
                    error=str(exc),
                )
                continue

    # ------------------------------------------------------------------
    # Exa AI semantic search (supplementary, non-blocking)
    # ------------------------------------------------------------------
    try:
        settings = get_settings()
        exa_key = settings.exa_api_key.get_secret_value()
        exa = ExaJobSearch(api_key=exa_key)
        if exa.available:
            exa_listings = await exa.search_jobs(
                query=request.query,
                location=request.location,
                num_results=min(request.limit, 10),
            )
            for listing in exa_listings:
                try:
                    _register(_listing_to_job(listing, user_id))
                except Exception:
                    continue
            logger.info("job_search.exa_results", count=len(exa_listings))
            job_searches_total.labels(platform="exa").inc()
            jobs_found_total.labels(platform="exa").inc(len(exa_listings))
    except Exception as exc:
        logger.debug("job_search.exa_skipped", reason=str(exc))

    if all_jobs:
        try:
            # ------------------------------------------------------------------
            # Phase 12 LLM Candidate Evaluation
            # ------------------------------------------------------------------
            candidate_model = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user_id))).scalar_one_or_none()
            if candidate_model:
                candidate = CandidateProfileSchema.model_validate(candidate_model, from_attributes=True)
                llm = LLMTaskRouter(LLMClient())
                matcher = CandidateJobMatcher(llm)

                async def _evaluate_job(j: Job) -> None:
                    if j.match_score is None:
                        try:
                            res = await matcher.match_candidate(candidate, j)
                            j.match_score = res.total_score or 0
                            
                            is_eligible = False
                            if hasattr(res, "eligibility") and hasattr(res.eligibility, "is_eligible"):
                                is_eligible = res.eligibility.is_eligible
                            elif hasattr(res, "is_eligible"):
                                is_eligible = res.is_eligible
                                
                            j.gcc_eligibility = {"is_eligible": is_eligible}
                            if res.strengths or res.gaps:
                                j.raw_data = {
                                    "strengths": [s.model_dump() if hasattr(s, "model_dump") else s.dict() if hasattr(s, "dict") else dict(s) for s in (res.strengths or [])],
                                    "gaps": res.gaps or [],
                                    "critical_gaps": res.critical_gaps or [],
                                    "recommendation": res.recommendation or "",
                                }
                        except Exception as eval_exc:
                            logger.error("job_search.evaluation_failed", job_id=j.platform_job_id, error=str(eval_exc))
                
                # Evaluate concurrently
                await asyncio.gather(*(_evaluate_job(j) for j in all_jobs))
                
            await db.commit()
            for job in all_jobs:
                await db.refresh(job)
        except Exception as exc:
            logger.error("job_search.commit_failed", error=str(exc))
            await db.rollback()
            all_jobs = []

    # Apply limit
    limited = all_jobs[: request.limit]
    items = [JobListingResponse.model_validate(j) for j in limited]

    return JobListResponse(
        items=items,
        total=len(all_jobs),
        page=1,
        page_size=request.limit,
        has_next=len(all_jobs) > request.limit,
    )


def _listing_to_job(listing: JobListing, user_id: str) -> Job:
    """Convert a platform ``JobListing`` to a ``Job`` database model.

    Args:
        listing: Normalized job listing from a platform scraper.

    Returns:
        A new unsaved ``Job`` model instance.
    """
    salary_range: str | None = None
    if listing.salary_min is not None and listing.salary_max is not None:
        salary_range = (
            f"{listing.salary_currency} "
            f"{listing.salary_min:,.0f} - {listing.salary_max:,.0f}"
        )
    elif listing.salary_min is not None:
        salary_range = f"{listing.salary_currency} {listing.salary_min:,.0f}+"
    elif listing.salary_max is not None:
        salary_range = f"Up to {listing.salary_currency} {listing.salary_max:,.0f}"

    skills_dict: dict[str, Any] | None = None
    if listing.skills_required or listing.skills_preferred:
        skills_dict = {
            "required": listing.skills_required,
            "preferred": listing.skills_preferred,
        }

    return Job(
        user_id=user_id,
        platform=listing.platform,
        platform_job_id=listing.platform_job_id,
        title=listing.title,
        company=listing.company,
        location=listing.location,
        url=listing.url,
        description=listing.description,
        salary_range=salary_range,
        job_type=listing.job_type or None,
        remote=listing.remote,
        skills_required=skills_dict,
        status="new",
    )


async def list_jobs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    status: str | None = None,
) -> JobListResponse:
    """List jobs with pagination and optional status filter.

    Args:
        db: Async database session.
        page: Page number (1-indexed).
        page_size: Items per page.
        status: Optional status filter.

    Returns:
        Paginated job list response.
    """
    page_size = min(page_size, MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

    query = select(Job)
    count_query = select(func.count(Job.id))

    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)

    query = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    jobs = list(result.scalars().all())

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    items = [JobListingResponse.model_validate(j) for j in jobs]

    return JobListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


async def get_job(db: AsyncSession, job_id: str) -> Job:
    """Get a single job by ID.

    Args:
        db: Async database session.
        job_id: UUID of the job.

    Returns:
        The Job model instance.

    Raises:
        RecordNotFoundError: If job does not exist.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise RecordNotFoundError("Job", job_id)
    return job


async def delete_job(db: AsyncSession, job_id: str) -> None:
    """Delete a job by ID.

    Args:
        db: Async database session.
        job_id: UUID of the job to delete.

    Raises:
        RecordNotFoundError: If job does not exist.
    """
    job = await get_job(db, job_id)
    await db.delete(job)
    await db.commit()
    logger.info("job_deleted", job_id=job_id)


async def analyze_job(
    db: AsyncSession,
    job_id: str,
    resume_id: str | None = None,
) -> CandidateMatchResult:
    from app.models.candidate_profile import CandidateProfile
    from app.schemas.candidate_profile import CandidateProfileSchema
    from app.core.llm.factory import build_llm_router_for_user
    from app.services.matching import CandidateJobMatcher
    from app.schemas.matching import CandidateMatchResult
    from sqlalchemy import select

    job = await get_job(db, job_id)
    
    candidate = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == job.user_id))).scalar_one_or_none()
    if not candidate:
        raise ValueError("No candidate profile found")

    schema = CandidateProfileSchema.model_validate(candidate)
    router = await build_llm_router_for_user(db, job.user_id)
    matcher = CandidateJobMatcher(router)
    
    result = await matcher.match_candidate(schema, job)
    
    # Save score to DB
    job.match_score = result.total_score
    await db.commit()
    
    return result


