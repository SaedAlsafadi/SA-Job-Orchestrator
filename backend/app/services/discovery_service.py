from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.models.job import Job
from app.core.connectors.workable_source import WorkableJobSource

logger = structlog.get_logger(__name__)

class DiscoveryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.sources = [WorkableJobSource()]

    def _get_source(self, url: str):
        # Naive implementation for MVP
        if "workable" in url:
            return self.sources[0]
        raise ValueError(f"No source connector supports URL: {url}")

    async def discover_and_store(self, user_id: str, url: str) -> List[Job]:
        source = self._get_source(url)
        raw_jobs = await source.discover_jobs(url)
        
        saved_jobs = []
        for raw in raw_jobs:
            normalized = source.normalize_job(raw)
            job = await self._upsert_job(user_id, normalized)
            saved_jobs.append(job)
            
        await self.db.commit()
        return saved_jobs

    async def _upsert_job(self, user_id: str, norm: Dict[str, Any]) -> Job:
        platform = norm["platform"]
        platform_job_id = norm["platform_job_id"]
        
        stmt = select(Job).where(
            Job.user_id == user_id,
            Job.platform == platform,
            Job.platform_job_id == platform_job_id
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # UPSERT mutable fields
            existing.title = norm["title"]
            existing.description = norm["description"]
            existing.requirements = norm["requirements"]
            existing.location = norm["location"]
            existing.application_url = norm["application_url"]
            # Preserve internal job ID, created_at, matching history
            return existing
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
                application_url=norm.get("application_url"),
                description=norm["description"],
                requirements=norm.get("requirements"),
                employment_type=norm.get("employment_type"),
                remote=norm.get("remote", False),
                work_model=norm.get("work_model"),
                posted_date=norm.get("posted_date"),
                raw_data=norm.get("raw_data", {}),
                status="new"
            )
            self.db.add(new_job)
            return new_job
