import asyncio
import json
from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.services.workflow_service import WorkflowService
from app.config import get_settings
from app.core.llm.client import LLMClient

async def main():
    async with async_session_factory() as session:
        candidate = (await session.execute(select(CandidateProfile).limit(1))).scalar_one_or_none()
        job = (await session.execute(select(Job).where(Job.title.ilike('%Software%')).limit(1))).scalar_one_or_none()
        
        if not candidate:
            print("No candidate found.")
            return
        if not job:
            job = (await session.execute(select(Job).limit(1))).scalar_one_or_none()
            if not job:
                print("No job found.")
                return
                
        print(f"Matching Candidate: {candidate.id} against Job: {job.title}")
        
        settings = get_settings()
        llm = LLMClient(settings)
        workflow = WorkflowService(db=session, llm_client=llm, )
        
        result = await workflow.match_candidate(str(candidate.id), str(job.id))
        
        print(json.dumps(result.model_dump(), indent=2, default=str))

if __name__ == '__main__':
    asyncio.run(main())



