"""Workflow API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Any

from app.api.deps import CurrentUser, get_tenant_db
from app.services.workflow_service import WorkflowService
from app.services.discovery_service import DiscoveryService
from app.services.matching import CandidateMatchResult
from app.core.llm.client import LLMClient
from app.core.llm.prompts.resume_tailor import TailoredResumeData
from app.models.candidate_profile import CandidateProfile
from app.models.application import Application, ApplicationRun
from app.core.connectors.workable_app import WorkableApplicationConnector
from app.services.question_engine import QuestionEngine

router = APIRouter()

def get_workflow_service(db: AsyncSession = Depends(get_tenant_db)) -> WorkflowService:
    return WorkflowService(db, LLMClient())

def get_discovery_service(db: AsyncSession = Depends(get_tenant_db)) -> DiscoveryService:
    return DiscoveryService(db)

class DiscoverRequest(BaseModel):
    url: str

class DiscoverResponse(BaseModel):
    discovered_jobs: int
    jobs: List[Any]

@router.get("/capabilities")
async def get_capabilities(
    user: CurrentUser,
    discovery: DiscoveryService = Depends(get_discovery_service)
):
    """Return a map of platform -> capabilities so frontend can disable unsupported features."""
    return discovery.get_all_capabilities()

@router.post("/discover")
async def discover_jobs(
    request: DiscoverRequest,
    user: CurrentUser,
    discovery: DiscoveryService = Depends(get_discovery_service)
):
    jobs = await discovery.discover_and_store(user.id, request.url)
    return {"discovered_jobs": len(jobs), "jobs": [{"id": j.id, "title": j.title, "company": j.company, "platform": j.platform} for j in jobs]}

class AnalyzeJobRequest(BaseModel):

    job_url: str | None = None
    job_description: str | None = None
    title: str | None = None
    company: str | None = None

class JobResponse(BaseModel):
    id: str
    title: str
    company: str

@router.post("/jobs/analyze")
async def analyze_job(
    request: AnalyzeJobRequest,
    user: CurrentUser,
    workflow: WorkflowService = Depends(get_workflow_service)
):
    if not request.job_url and not request.job_description:
        raise HTTPException(status_code=400, detail="Must provide job_url or job_description")
        
    job = await workflow.analyze_job(
        job_description=request.job_description or "",
        title=request.title or "Unknown Title",
        company=request.company or "Unknown Company",
        user_id=user.id
    )
    return JobResponse(id=job.id, title=job.title, company=job.company)

@router.post("/jobs/{job_id}/match")
async def match_candidate(
    job_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
    workflow: WorkflowService = Depends(get_workflow_service)
) -> CandidateMatchResult:
    candidate = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))).scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
        
    return await workflow.match_candidate(candidate.id, job_id)

@router.post("/jobs/{job_id}/tailor-resume")
async def tailor_resume(
    job_id: str,
    match_result: CandidateMatchResult,
    user: CurrentUser,
    db: AsyncSession = Depends(get_tenant_db),
    workflow: WorkflowService = Depends(get_workflow_service)
) -> TailoredResumeData:
    candidate = (await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))).scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
        
    return await workflow.tailor_resume(candidate.id, job_id, match_result)

@router.post("/jobs/{job_id}/prepare-application")
async def prepare_application(
    job_id: str,
    data: TailoredResumeData,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_tenant_db)
):
    from app.models.job import Job
    from app.models.application import Application, ApplicationRun
    from app.models.candidate_profile import CandidateProfile
    from app.services.application_runner import run_application_preparation
    from app.db.session import async_session_maker
    
    # 1. Verify Job and Profile
    result = await db.execute(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
        
    result = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Profile not found")

    # 2. Find or Create Application
    result = await db.execute(select(Application).where(Application.job_id == job_id, Application.user_id == user.id))
    app_entity = result.scalar_one_or_none()
    if not app_entity:
        app_entity = Application(job_id=job_id, user_id=user.id, status="preparing")
        db.add(app_entity)
        await db.flush()
    else:
        app_entity.status = "preparing"
        
    # 3. Create Run
    from datetime import datetime
    run = ApplicationRun(
        application_id=app_entity.id,
        user_id=user.id,
        status="running",
        started_at=datetime.utcnow()
    )
    db.add(run)
    await db.commit()
    await db.refresh(app_entity)
    await db.refresh(run)

    # 4. Trigger Background Task
    # Note: async_session_maker is typically accessible from app.db.session
    background_tasks.add_task(
        run_application_preparation,
        run_id=run.id,
        app_id=app_entity.id,
        job_url=job.application_url or job.url,
        db_session_maker=async_session_maker,
        profile_data={"identity": profile.identity, "preferences": profile.preferences},
        resume_path="data/storage/mock_resume.pdf" # Mock for now
    )
    
    return {"message": "Application preparation started", "run_id": run.id, "application_id": app_entity.id}
