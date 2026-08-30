from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, UTC
import structlog

from app.models.job import Job
from app.core.connectors.workable_source import WorkableJobSource
from app.core.connectors.greenhouse_source import GreenhouseJobSource
from app.core.connectors.lever_source import LeverJobSource
from app.services.monitoring.utils import get_canonical_url, compute_content_hash

logger = structlog.get_logger(__name__)

class DiscoveryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.sources = [WorkableJobSource(), GreenhouseJobSource(), LeverJobSource()]

    def _get_source(self, url: str):
        # Naive implementation for MVP
        if "workable" in url:
            return self.sources[0]
        elif "greenhouse" in url:
            return self.sources[1]
        elif "lever" in url:
            return self.sources[2]
        raise ValueError(f"No source connector supports URL: {url}")

    def get_all_capabilities(self) -> Dict[str, Any]:
        return {s.name(): s.capabilities().model_dump() for s in self.sources}

    async def discover_and_store(self, user_id: str, url: str) -> List[Tuple[Job, bool, bool]]:
        source = self._get_source(url)
        raw_jobs = await source.discover_jobs(url)
        
        saved_jobs = []
        for raw in raw_jobs:
            normalized = source.normalize_job(raw)
            job, is_new, is_changed = await self._upsert_job(user_id, normalized)
            saved_jobs.append((job, is_new, is_changed))
            
        await self.db.commit()
        return saved_jobs

    async def _upsert_job(self, user_id: str, norm: Dict[str, Any]) -> Tuple[Job, bool, bool]:
        platform = norm["platform"]
        platform_job_id = norm["platform_job_id"]
        
        canonical_url = get_canonical_url(norm.get("url", ""))
        content_hash = compute_content_hash(norm)
        
        stmt = select(Job).where(
            Job.user_id == user_id,
            Job.platform == platform,
            Job.platform_job_id == platform_job_id
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            is_new = False
            is_changed = False
            
            if existing.content_hash != content_hash:
                is_changed = True
                existing.content_hash = content_hash
                existing.title = norm["title"]
                existing.description = norm["description"]
                existing.requirements = norm.get("requirements")
                existing.location = norm["location"]
                existing.application_url = norm.get("application_url")
                existing.salary_range = norm.get("salary_range")
                existing.salary = norm.get("salary")
                existing.job_type = norm.get("job_type")
                existing.employment_type = norm.get("employment_type")
                existing.remote = norm.get("remote", False)
                existing.work_model = norm.get("work_model")
                # update timestamp to trigger re-evaluation logically if needed
                existing.updated_at = datetime.now(UTC)
                
            if existing.canonical_url != canonical_url:
                existing.canonical_url = canonical_url
                
            return existing, is_new, is_changed
        else:
            new_job = Job(
                user_id=user_id,
                platform=platform,
                platform_job_id=platform_job_id,
                title=norm["title"],
                company=norm["company"],
                location=norm["location"],
                country=norm.get("country"),
                city=norm.get("city"),
                url=norm["url"],
                canonical_url=canonical_url,
                content_hash=content_hash,
                first_seen_at=datetime.now(UTC),
                application_url=norm.get("application_url"),
                description=norm["description"],
                requirements=norm.get("requirements"),
                salary_range=norm.get("salary_range"),
                salary=norm.get("salary"),
                job_type=norm.get("job_type"),
                employment_type=norm.get("employment_type"),
                remote=norm.get("remote", False),
                work_model=norm.get("work_model"),
                posted_date=norm.get("posted_date"),
                raw_data=norm.get("raw_data", {}),
                status="new"
            )
            self.db.add(new_job)
            return new_job, True, False
