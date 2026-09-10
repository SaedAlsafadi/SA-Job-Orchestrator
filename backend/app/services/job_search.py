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
from app.models.tailoring import CVTailoringSession
from app.models.application import Application
from app.models.application_package import ApplicationPackage
from app.models.application_route import ApplicationRoute
from app.models.candidate_profile import CandidateProfile
from app.schemas.candidate_profile import CandidateProfileSchema
from app.services.matching import CandidateJobMatcher
from app.core.llm.client import LLMClient
from app.core.llm.router import LLMTaskRouter
import asyncio
from app.observability.metrics import job_searches_total, jobs_found_total
from app.schemas.matching import CandidateMatchResult
from app.schemas.job import (
    OpportunityOperationalState,
    JobListingResponse,
    JobListResponse,
    JobSearchRequest,
)

logger = structlog.get_logger(__name__)


def _stored_match_score(score: int | float | None) -> float | None:
    """Persist new match scores in the canonical 0..1 representation."""
    if score is None:
        return None
    value = float(score)
    return value / 100 if abs(value) > 1 else value


async def _operational_states(db: AsyncSession, jobs: list[Job]) -> dict[str, dict[str, Any]]:
    """Batch related workflow records for opportunity-card decisions."""
    ids = [job.id for job in jobs]
    if not ids:
        return {}
    sessions = list((await db.execute(select(CVTailoringSession).where(CVTailoringSession.job_id.in_(ids)))).scalars())
    tailored = list((await db.execute(select(Resume).where(Resume.job_id.in_(ids), Resume.type == "tailored"))).scalars())
    applications = list((await db.execute(select(Application).where(Application.job_id.in_(ids)))).scalars())
    packages = list((await db.execute(select(ApplicationPackage).where(ApplicationPackage.job_id.in_(ids), ApplicationPackage.is_current.is_(True)))).scalars())
    routes = list((await db.execute(select(ApplicationRoute).where(ApplicationRoute.job_id.in_(ids)))).scalars())

    def latest(rows: list[Any], job_id: str) -> Any | None:
        matches = [row for row in rows if row.job_id == job_id]
        return max(matches, key=lambda row: row.updated_at or row.created_at) if matches else None

    states: dict[str, dict[str, Any]] = {}
    for job in jobs:
        session = latest(sessions, job.id)
        resume = next((r for r in tailored if session and r.id == session.final_resume_id), None) or latest(tailored, job.id)
        application = latest(applications, job.id)
        package = latest(packages, job.id)
        route = next((r for r in routes if package and r.id == package.route_id), None)
        if route is None:
            candidates = [r for r in routes if r.job_id == job.id]
            route = next((r for r in candidates if r.is_preferred), None) or (latest(candidates, job.id) if candidates else None)
        route_type = route.route_type.upper() if route else None
        package_ready = False
        if package:
            package_ready = bool(package.resume_id and package.cover_letter_text)
            if route_type == "EMAIL":
                package_ready = package_ready and bool(package.email_to and package.email_subject and package.email_body)
            package_ready = package_ready and package.qa_verdict != "blocked"
        raw = job.raw_data if isinstance(job.raw_data, dict) else {}
        analysis_keys = {"strengths", "gaps", "critical_gaps", "recommendation", "requirement_analysis"}
        states[job.id] = {
            "match_exists": bool(analysis_keys.intersection(raw) or job.match_score is not None),
            "tailoring_session_id": session.id if session else None,
            "tailoring_status": str(session.status) if session else None,
            "tailored_resume_id": resume.id if resume else None,
            # Modern sessions prove verification explicitly. Legacy generated
            # tailored résumés predate session tracking, so their persisted
            # document artifact + canonical content is the best existing proof.
            "tailored_resume_verified": bool(
                resume
                and (
                    (session and str(session.status) == "verified" and session.final_resume_id == resume.id)
                    or (resume.content_text and (resume.file_path_pdf or resume.file_path_docx))
                )
            ),
            "application_id": application.id if application else None,
            "application_status": str(application.status) if application else None,
            "package_id": package.id if package else None,
            "package_version": package.version if package else None,
            "package_ready": package_ready,
            "package_approved": bool(package and package.approval_id and package.approved_at),
            "route_type": route_type,
            "route_url": route.url if route else None,
        }
    return states


async def _job_responses(db: AsyncSession, jobs: list[Job]) -> list[JobListingResponse]:
    states = await _operational_states(db, jobs)
    responses: list[JobListingResponse] = []
    for job in jobs:
        response = JobListingResponse.model_validate(job)
        response.operational_state = OpportunityOperationalState(**states[job.id])
        responses.append(response)
    return responses


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
                            j.match_score = _stored_match_score(res.total_score or 0)
                            
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
    items = await _job_responses(db, limited)

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
    source_type: str | None = None,
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

    if source_type:
        query = query.where(Job.source_type == source_type)
        count_query = count_query.where(Job.source_type == source_type)

    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)

    query = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    jobs = list(result.scalars().all())

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    items = await _job_responses(db, jobs)

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
    from sqlalchemy.orm import selectinload
    result = await db.execute(select(Job).options(selectinload(Job.routes)).where(Job.id == job_id))
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
    language: str = "en",
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
    
    result = await matcher.match_candidate(schema, job, language=language)
    
    # Save score to DB
    job.match_score = _stored_match_score(result.total_score)
    await db.commit()
    
    return result



