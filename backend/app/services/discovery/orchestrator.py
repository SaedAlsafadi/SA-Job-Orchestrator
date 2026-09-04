"""Autonomous Discovery Orchestrator."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.search_profile import SearchProfile
from app.models.company_watch import CompanyWatch
from app.models.discovery_run import DiscoveryRun
from app.models.discovery_event import DiscoveryEvent
from app.models.job import Job
from app.models.application import Application
from app.models.candidate_profile import CandidateProfile

from app.services.discovery.query_planner import QueryPlanner
from app.core.job_discovery.providers.exa_provider import ExaDiscoveryProvider
from app.core.job_discovery.providers.ats_providers import WorkableProvider, GreenhouseProvider, LeverProvider
from app.core.job_discovery.providers.bayt_provider import BaytDiscoveryProvider
from app.services.monitoring.utils import compute_content_hash, get_canonical_url
from app.services.application_route_resolver import ApplicationRouteResolver
from app.services.matching import CandidateJobMatcher
from app.schemas.candidate_profile import CandidateProfileSchema

logger = logging.getLogger(__name__)

class DiscoveryOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.query_planner = QueryPlanner()
        # Instantiate providers
        self.providers = {
            "exa": ExaDiscoveryProvider(),
            "workable": WorkableProvider(),
            "greenhouse": GreenhouseProvider(),
            "lever": LeverProvider(),
            "bayt": BaytDiscoveryProvider()
        }
        
    async def get_candidate_profile(self, user_id: str) -> Optional[CandidateProfileSchema]:
        """Fetch candidate profile for matching."""
        stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        result = await self.db.execute(stmt)
        profile_model = result.scalar_one_or_none()
        if not profile_model:
            return None
        return CandidateProfileSchema.model_validate(profile_model, from_attributes=True)

    async def _check_active_application(self, user_id: str, content_hash: str) -> bool:
        """Prevent duplicated preparation by checking for active applications."""
        stmt = select(Application).join(Job).where(
            and_(
                Job.content_hash == content_hash,
                Application.user_id == user_id,
                Application.status.in_([
                    "PREPARING", "READY", "WAITING_FOR_REVIEW", 
                    "SUBMITTING", "APPLIED", "SUBMISSION_UNKNOWN"
                ])
            )
        )
        result = await self.db.execute(stmt)
        return result.first() is not None

    async def run_search_profile(self, profile_id: str, dry_run: bool = False) -> Dict[str, Any]:
        """Execute autonomous search pipeline for a global SearchProfile."""
        profile = await self.db.get(SearchProfile, profile_id)
        if not profile:
            raise ValueError(f"SearchProfile {profile_id} not found.")

        stats = {
            "queries_generated": 0,
            "providers_used": [],
            "raw_results": 0,
            "unique_jobs": 0,
            "eligible": 0,
            "ineligible": 0,
            "shortlisted": 0,
            "selected_for_prep": 0,
            "skipped_reasons": {}
        }
        
        run = DiscoveryRun(
            search_profile_id=profile.id,
            user_id=profile.user_id,
            status="running",
            queries_generated=0
        )
        self.db.add(run)
        await self.db.commit()
        
        queries = self.query_planner.plan_queries(profile)
        stats["queries_generated"] = len(queries)
        run.queries_generated = len(queries)
        
        candidate_data = await self.get_candidate_profile(profile.user_id)
        
        global_providers = [p for p in self.providers.values() if p.capabilities().global_search]
        stats["providers_used"] = [p.name() for p in global_providers]
        
        provider_errors = {}
        all_raw_jobs = []
        
        # 1. FAN OUT TO PROVIDERS
        for provider in global_providers:
            for query in queries:
                try:
                    results = await provider.search(query=query)
                    for r in results:
                        # inject provenance early
                        r["__discovery_provider"] = provider.name()
                        r["__discovery_query"] = query
                        r["__provider_ref"] = provider
                    all_raw_jobs.extend(results)
                except Exception as e:
                    logger.error(f"Provider {provider.name()} failed on query '{query}': {e}")
                    provider_errors[provider.name()] = str(e)
                    
        stats["raw_results"] = len(all_raw_jobs)
        
        return await self._process_pipeline(profile, all_raw_jobs, candidate_data, run, stats, dry_run)

    async def _process_pipeline(
        self, profile, all_raw_jobs: List[Dict], candidate_data: Optional[CandidateProfileSchema], 
        run: DiscoveryRun, stats: Dict, dry_run: bool
    ) -> Dict[str, Any]:
        
        # 2. NORMALIZE & CANONICALIZE
        unique_map = {} # content_hash -> job data
        events_map = {} # content_hash -> list of discovery events
        
        for raw in all_raw_jobs:
            provider = raw.pop("__provider_ref")
            provider_name = raw.pop("__discovery_provider")
            query = raw.pop("__discovery_query")
            
            norm = provider.normalize(raw)
            url = norm.get("url") or ""
            norm["canonical_url"] = get_canonical_url(url)
            
            chash = compute_content_hash(norm)
            
            event = {
                "provider": provider_name,
                "query": query,
                "source_url": url,
                "discovered_at": datetime.now(UTC)
            }
            
            if chash not in unique_map:
                unique_map[chash] = norm
                events_map[chash] = [event]
            else:
                events_map[chash].append(event)
                
        stats["unique_jobs"] = len(unique_map)
        run.jobs_found = len(all_raw_jobs)
        run.jobs_new = len(unique_map)
        
        def skip(chash, reason):
            stats["skipped_reasons"][reason] = stats["skipped_reasons"].get(reason, 0) + 1
            stats["ineligible"] += 1
            
        candidates_for_llm = []
        
        # 3. DETERMINISTIC PRE-FILTER & DEDUPLICATION
        for chash, norm in unique_map.items():
            # Check Active Application Deduplication
            if await self._check_active_application(profile.user_id, chash):
                skip(chash, "already active application")
                continue
                
            # Check Title Mismatch (Cheap)
            title = (norm.get("title") or "").lower()
            if profile.target_roles:
                if not any(r.lower() in title for r in profile.target_roles + (profile.role_aliases or [])):
                    skip(chash, "obvious role mismatch")
                    continue
                    
            # Check Location Mismatch (Cheap)
            loc = (norm.get("location") or "").lower()
            if profile.preferred_countries or profile.preferred_cities:
                valid_locs = [l.lower() for l in (profile.preferred_countries or []) + (profile.preferred_cities or [])]
                if loc and not any(vl in loc for vl in valid_locs):
                    # Only skip if location is explicitly stated and definitely doesn't match
                    if not norm.get("remote"):
                        skip(chash, "obvious location mismatch")
                        continue

            stats["eligible"] += 1
            candidates_for_llm.append((chash, norm))

        run.jobs_eligible = stats["eligible"]

        # 4. ELIGIBILITY & MATCH (including LLM Shortlist)
        # Note: If there are many, we might want to limit LLM calls, but for now we evaluate eligible ones.
        matched_jobs = []
        from app.core.llm.client import LLMClient
        from app.core.llm.router import LLMTaskRouter
        matching_service = CandidateJobMatcher(LLMTaskRouter(LLMClient()))
        
        for chash, norm in candidates_for_llm:
            if not candidate_data:
                # Without candidate data, everything passes match with 0 score
                matched_jobs.append((chash, norm, 0.0, None))
                stats["shortlisted"] += 1
                continue
                
            # Prepare canonical Job object for MatchingService
            temp_job = Job(
                title=norm["title"],
                company=norm["company"],
                description=norm["description"],
                requirements=norm.get("requirements"),
                location=norm["location"]
            )
            
            # Deterministic Match & LLM Qualitative Evaluation
            try:
                eval_result = await matching_service.evaluate_match(candidate_data, temp_job)
                
                # Check if it's eligible
                if not eval_result.eligibility.is_eligible:
                    skip(chash, "failed eligibility check: " + ", ".join(eval_result.eligibility.reasons))
                    continue
                    
                score = eval_result.total_score or 0
                if score >= profile.minimum_match_score:
                    matched_jobs.append((chash, norm, score, eval_result))
                    stats["shortlisted"] += 1
                else:
                    skip(chash, f"below final threshold ({score} < {profile.minimum_match_score})")
            except Exception as e:
                logger.error(f"Matching failed for {chash}: {e}")
                skip(chash, "matching error")

        run.jobs_matched = stats["shortlisted"]

        # 5. RANKING
        def rank_score(item):
            # item = (chash, norm, match_score, eval_result)
            chash, norm, match_score, eval_result = item
            # Freshness bonus: +5 points if discovered in last 24h (mocked by received_at)
            freshness_bonus = 5.0 # simplifying freshness since all are newly pulled
            # In a real scenario we'd query DB for first_seen_at
            return match_score + freshness_bonus
            
        matched_jobs.sort(key=rank_score, reverse=True)
        
        # 6. SELECT TOP N & PREPARE
        resolver = ApplicationRouteResolver()
        selected_for_prep = 0
        cap_cycle = profile.max_preparations_per_cycle
        cap_day = profile.max_preparations_per_day
        
        # Check how many apps prepared today
        today = datetime.now(UTC).date()
        # In a real app we'd use a DB query for today's preparations, but simplified here
        # or we just assume we have the count. Let's do a simple count.
        stmt_today = select(func.count(Application.id)).where(
            and_(
                Application.user_id == profile.user_id,
                func.date(Application.created_at) == today
            )
        )
        try:
            apps_today = (await self.db.execute(stmt_today)).scalar() or 0
        except Exception:
            apps_today = 0
            
        remaining_today = max(0, cap_day - apps_today)
        cap = min(cap_cycle, remaining_today)
        
        if cap <= 0:
            stats["skipped_reasons"]["daily preparation capacity reached"] = len(matched_jobs)
            matched_jobs = [] # clear them since we can't process any
            
        for chash, norm, score, eval_result in matched_jobs:
            if selected_for_prep >= cap:
                skip(chash, "preparation capacity reached")
                continue
                
            # Persist Job & Discovery Events
            job = await self._persist_job(profile.user_id, chash, norm, events_map[chash])
            
            # Resolve Route
            routes = await resolver.resolve(job)
            for r in routes:
                self.db.add(r)
            await self.db.commit()
            
            if not routes or routes[0].requires_human:
                skip(chash, "route unresolved or requires human")
                continue

            selected_for_prep += 1
            
            if not dry_run:
                app = Application(
                    user_id=profile.user_id,
                    job_id=job.id,
                    status="PREPARING",
                    match_score=score
                )
                self.db.add(app)
                await self.db.commit()
                
                # Enqueue Preparation Task securely
                from app.config.settings import get_settings
                settings = get_settings()
                if settings.redis_url:
                    try:
                        from arq import create_pool
                        from arq.connections import RedisSettings
                        redis_settings = RedisSettings.from_dsn(settings.redis_url)
                        redis = await create_pool(redis_settings)
                        await redis.enqueue_job("prepare_application_run", app.id)
                        await redis.aclose()
                    except Exception as e:
                        logger.error(f"Failed to enqueue preparation for {app.id}: {e}")
                else:
                    logger.warning(f"No Redis URL, cannot enqueue preparation for {app.id}")

        stats["selected_for_prep"] = selected_for_prep
        run.jobs_selected = selected_for_prep
        run.skipped_reasons = stats["skipped_reasons"]
        run.status = "success"
        
        await self.db.commit()
        return stats
        
    async def _persist_job(self, user_id: str, chash: str, norm: dict, events: list) -> Job:
        """Persist or retrieve Canonical Job and attach discovery provenance."""
        stmt = select(Job).where(Job.content_hash == chash)
        res = await self.db.execute(stmt)
        job = res.scalar_one_or_none()
        
        if not job:
            job = Job(
                user_id=user_id,
                platform="exa", # legacy fallback
                platform_job_id=norm.get("platform_job_id") or chash,
                title=norm["title"],
                company=norm["company"],
                description=norm["description"],
                location=norm["location"],
                url=norm["url"],
                remote=norm.get("remote", False),
                employment_type=norm.get("employment_type"),
                source_type="search",
                content_hash=chash,
                received_at=datetime.now(UTC),
                first_seen_at=datetime.now(UTC),
                status="new"
            )
            self.db.add(job)
            await self.db.commit()
            await self.db.refresh(job)
            
        for e in events:
            de = DiscoveryEvent(
                job_id=job.id,
                discovery_provider=e["provider"],
                discovery_query=e["query"],
                source_url=e["source_url"],
                discovered_at=e["discovered_at"]
            )
            self.db.add(de)
            
        await self.db.commit()
        return job



