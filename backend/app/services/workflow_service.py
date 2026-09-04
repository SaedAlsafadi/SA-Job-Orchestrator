"""Workflow service for the application pipeline."""

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.enums import ApplicationStatus, ResumeType
from app.schemas.candidate_profile import CandidateProfileSchema
from app.services.matching import CandidateJobMatcher
from app.schemas.matching import CandidateMatchResult
from app.core.llm.client import LLMClient
from app.core.llm.router import LLMTaskRouter, LLMTask
from app.core.documents.pdf_renderer import PlaywrightPDFRenderer
from app.core.llm.prompts.resume_tailor import TailoredResumeData


class WorkflowService:
    def __init__(self, db: AsyncSession, llm_router: LLMTaskRouter):
        self.db = db
        self.llm_router = llm_router
        self.matcher = CandidateJobMatcher(llm_router)
        self.pdf_renderer = PlaywrightPDFRenderer()

    async def analyze_job(self, job_description: str, title: str, company: str, user_id: str) -> Job:
        """Extract structured fields from a pasted job description and save it."""
        # Simple extraction for demo (a real implementation would call the LLM to structure this fully)
        job = Job(
            user_id=user_id,
            platform="manual",
            platform_job_id=uuid.uuid4().hex[:12],
            title=title,
            company=company,
            description=job_description,
            url="manual",
            gcc_eligibility={}
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def match_candidate(self, candidate_id: str, job_id: str) -> CandidateMatchResult:
        """Evaluate candidate vs job."""
        from sqlalchemy import select
        
        # Load candidate
        candidate_model = (await self.db.execute(select(CandidateProfile).where(CandidateProfile.id == candidate_id))).scalar_one_or_none()
        if not candidate_model:
            raise ValueError("Candidate not found")
            
        candidate_schema = CandidateProfileSchema(
            identity=candidate_model.identity,
            location=candidate_model.location,
            employment=candidate_model.employment,
            work_authorization=candidate_model.work_authorization,
            education=candidate_model.education,
            experience=candidate_model.experience,
            skills=candidate_model.skills,
            projects=candidate_model.projects,
            certifications=candidate_model.certifications,
            preferences=candidate_model.preferences
        )
        
        # Load job
        job = (await self.db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
        if not job:
            raise ValueError("Job not found")

        return await self.matcher.match_candidate(candidate_schema, job)

    async def tailor_resume(self, candidate_id: str, job_id: str, match_result: CandidateMatchResult) -> TailoredResumeData:
        """Generate tailored resume JSON."""
        from sqlalchemy import select
        
        candidate_model = (await self.db.execute(select(CandidateProfile).where(CandidateProfile.id == candidate_id))).scalar_one_or_none()
        job = (await self.db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
        
        system_prompt = (
            "You are an expert resume writer. Tailor this resume to the job description. "
            "CRITICAL: Do NOT invent experience, employers, dates, or technologies. "
            "Use ONLY facts provided in the Candidate Profile. "
            "Highlight strengths related to the job."
        )
        
        prompt = f"CANDIDATE:\n{json.dumps(candidate_model.experience)}\n\nJOB:\n{job.description}"
        
        try:
            tailored_data = await self.llm_router.complete_with_structured_output(
                task=LLMTask.CV_TAILOR,
                prompt=prompt,
                system_prompt=system_prompt,
                output_schema=TailoredResumeData,
                purpose="resume_tailor"
            )
            return tailored_data
        except Exception as e:
            import logging
            logging.error(f"Resume tailor failed: {e}")
            from app.schemas.resume import TailoredResumeData, TailoredExperience
            
            # Deterministic fallback mapping
            exp = []
            for e in candidate_model.experience:
                exp.append(TailoredExperience(
                    id=e.get("id", "fallback_exp"),
                    title=e.get("title", ""),
                    company=e.get("company", ""),
                    date_range=e.get("date_range", ""),
                    bullets=e.get("bullets", [])
                ))
            
            return TailoredResumeData(
                professional_summary=candidate_model.identity.get("professional_summary", ""),
                experience=exp,
                skills=candidate_model.skills
            )

    async def generate_resume_pdf(self, tailored_data: TailoredResumeData, user_id: str, job_id: str) -> Resume:
        """Generate PDF and store Resume record."""
        # Convert Pydantic model to dictionary for Jinja2 context
        context = tailored_data.model_dump()
        
        # Ensure we have a place to write
        output_dir = Path("./data/storage/resumes")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_name = f"tailored_{uuid.uuid4().hex[:8]}.pdf"
        output_path = output_dir / file_name
        
        await self.pdf_renderer.render("modern", context, output_path)
        
        resume = Resume(
            user_id=user_id,
            job_id=job_id,
            name=f"Tailored for Job {job_id}",
            type=ResumeType.TAILORED,
            file_path_pdf=str(output_path),
            audit_metadata={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "job_id": job_id,
                "model_provider": "gemini",
                "model_name": "gemini-3.5-flash"
            }
        )
        self.db.add(resume)
        await self.db.commit()
        await self.db.refresh(resume)
        return resume

    async def prepare_application(self, user_id: str, job_id: str, resume_id: str) -> Application:
        """Create Application record in READY state."""
        app = Application(
            user_id=user_id,
            job_id=job_id,
            resume_id=resume_id,
            status=ApplicationStatus.READY,
            audit_metadata={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "job_id": job_id
            }
        )
        self.db.add(app)
        await self.db.commit()
        return app


