"""Core logic for monitoring cycles."""

from datetime import datetime, UTC, timedelta
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
import time

from app.models.monitoring import MonitoringSchedule, MonitoringRun
from app.models.job import Job
from app.models.application import Application
from app.models.enums import ApplicationStatus
from app.services.discovery_service import DiscoveryService
from app.services.eligibility import evaluate_eligibility
from app.services.matching import CandidateJobMatcher
from app.core.llm.client import LLMClient
from app.schemas.candidate_profile import CandidateProfileSchema
from app.models.candidate_profile import CandidateProfile
from app.services.monitoring.locking import acquire_monitoring_lock, MonitoringLockError

logger = structlog.get_logger(__name__)

class MonitoringService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.discovery = DiscoveryService(db)
        self.llm_client = LLMClient()
        self.matching = CandidateJobMatcher(self.llm_client)

    async def get_candidate_profile(self, user_id: str) -> CandidateProfileSchema | None:
        """Get the active candidate profile for matching."""
        stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        result = await self.db.execute(stmt)
        profile_model = result.scalar_one_or_none()
        if not profile_model:
            return None
        return CandidateProfileSchema.model_validate(profile_model, from_attributes=True)

    async def check_active_application(self, user_id: str, job_id: str) -> bool:
        """Check if an active application already exists for this candidate/job combo."""
        stmt = select(Application).where(
            Application.user_id == user_id,
            Application.job_id == job_id,
            Application.status.in_([
                ApplicationStatus.PREPARING,
                ApplicationStatus.READY,
                ApplicationStatus.WAITING_FOR_REVIEW,
                ApplicationStatus.SUBMITTING,
                ApplicationStatus.APPLIED
            ])
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _process_job(
        self, 
        job: Job, 
        is_new: bool, 
        is_changed: bool, 
        profile: CandidateProfileSchema,
        schedule: MonitoringSchedule,
        run_stats: dict
    ) -> dict | None:
        """Evaluate a single job and return it if it should be prepared."""
        if not is_new and not is_changed:
            run_stats["unchanged"] += 1
            return None

        # Check existing application deduplication
        has_active = await self.check_active_application(job.user_id, job.id)
        if has_active:
            run_stats["duplicates"] += 1
            return None

        # Eligibility check
        eligibility = evaluate_eligibility(profile, job)
        if not eligibility.is_eligible:
            run_stats["ineligible"] += 1
            job.status = "rejected"
            await self.db.commit()
            return None
        
        run_stats["eligible"] += 1
        
        # LLM Match check
        match_result = await self.matching.match_candidate(profile, job)
        score = match_result.score if match_result.score else 0.0
        
        job.match_score = score
        await self.db.commit()
        
        if score < schedule.match_threshold:
            run_stats["low_match"] += 1
            return None
            
        run_stats["high_match"] += 1
        
        # Return for ranking
        return {
            "job": job,
            "score": score
        }

    async def trigger_preparation(self, job: Job):
        """Transition job to PREPARING and dispatch worker task."""
        from app.workers.tasks import prepare_application_run
        
        # Create application record
        app_record = Application(
            user_id=job.user_id,
            job_id=job.id,
            status=ApplicationStatus.PREPARING
        )
        self.db.add(app_record)
        job.status = "preparing"
        await self.db.commit()
        
        # Dispatch Arq task
        from arq import create_pool
        from app.config.settings import get_settings
        settings = get_settings()
        if settings.redis_url:
            from arq.connections import RedisSettings
            redis_settings = RedisSettings.from_dsn(settings.redis_url)
            redis = await create_pool(redis_settings)
            await redis.enqueue_job("prepare_application_run", app_record.id)
            await redis.aclose()
        else:
            logger.warning("No Redis URL, cannot enqueue preparation task automatically")

    async def run_monitoring_cycle(self, schedule_id: str, dry_run: bool = False) -> dict:
        """Run a single monitoring cycle for a given schedule."""
        start_time = time.time()
        
        # 1. Fetch Schedule
        stmt = select(MonitoringSchedule).where(MonitoringSchedule.id == schedule_id)
        result = await self.db.execute(stmt)
        schedule = result.scalar_one_or_none()
        
        if not schedule or not schedule.is_active:
            return {"status": "skipped", "reason": "Inactive or missing schedule"}

        # Initialize Run record
        run_record = MonitoringRun(
            schedule_id=schedule.id,
            user_id=schedule.user_id,
            status="running"
        )
        self.db.add(run_record)
        await self.db.commit()

        stats = {
            "found": 0, "new": 0, "changed": 0, "unchanged": 0,
            "duplicates": 0, "eligible": 0, "ineligible": 0,
            "high_match": 0, "low_match": 0, "selected": 0
        }
        
        try:
            # 2. Acquire Lock
            async with acquire_monitoring_lock(self.db, schedule.platform, schedule.source):
                
                # Fetch candidate profile
                profile = await self.get_candidate_profile(schedule.user_id)
                if not profile:
                    raise ValueError(f"Candidate profile not found for user {schedule.user_id}")
                
                # 3. Discover Jobs
                discovered = await self.discovery.discover_and_store(schedule.user_id, schedule.source)
                stats["found"] = len(discovered)
                
                high_match_candidates = []
                
                for job, is_new, is_changed in discovered:
                    if is_new:
                        stats["new"] += 1
                    elif is_changed:
                        stats["changed"] += 1
                    
                    candidate_job = await self._process_job(job, is_new, is_changed, profile, schedule, stats)
                    if candidate_job:
                        high_match_candidates.append(candidate_job)
                
                # 4. Rank and Select
                # Sort by score descending
                high_match_candidates.sort(key=lambda x: x["score"], reverse=True)
                
                # Take top N
                selected_jobs = high_match_candidates[:schedule.max_preparations_per_cycle]
                stats["selected"] = len(selected_jobs)
                
                # 5. Prepare Selected
                if not dry_run:
                    for item in selected_jobs:
                        await self.trigger_preparation(item["job"])
                
                # 6. Update Schedule & Run
                schedule.last_checked_at = datetime.now(UTC)
                run_record.status = "success"
                
        except MonitoringLockError as e:
            logger.info(f"Skipping overlapping cycle for {schedule.id}: {e}")
            run_record.status = "skipped"
            run_record.error = str(e)
            
        except Exception as e:
            logger.exception(f"Monitoring cycle failed for schedule {schedule.id}")
            run_record.status = "failed"
            run_record.error = str(e)
            
        finally:
            run_record.duration = time.time() - start_time
            run_record.jobs_found = stats["found"]
            run_record.jobs_new = stats["new"]
            run_record.jobs_eligible = stats["eligible"]
            run_record.jobs_matched = stats["high_match"]
            run_record.jobs_selected = stats["selected"]
            await self.db.commit()
            
        return {
            "status": run_record.status,
            "duration": run_record.duration,
            "stats": stats,
            "error": run_record.error
        }
