import asyncio
from app.core.llm.client import LLMClient
from app.core.llm.router import LLMTaskRouter
from app.services.matching import CandidateJobMatcher
from app.schemas.candidate_profile import CandidateProfileSchema
from app.models.job import Job

async def run_smoke_test():
    router = LLMTaskRouter(LLMClient())
    matcher = CandidateJobMatcher(router)
    
    candidate = CandidateProfileSchema(
        user_id="u1",
        version=1,
        headline="Senior Python Developer",
        summary="Experienced backend engineer with FastAPI and PostgreSQL.",
        skills=[{"skill": "Python"}, {"skill": "FastAPI"}],
        experience=[
            {"company": "Tech Corp", "title": "Software Engineer", "description": "Built APIs with Python and FastAPI."}
        ],
        education=[],
        languages=[]
    )
    
    job = Job(
        title="Backend Engineer",
        company="Startup",
        description="We are looking for a backend engineer. You must know Python and FastAPI. AWS experience is a plus.",
        requirements="Python, FastAPI, AWS",
        responsibilities="Build APIs",
        is_normalized=True
    )
    
    res = await matcher.match_candidate(candidate, job)
    
    print(f"Verdict: {res.verdict}")
    print(f"Confidence: {res.confidence}")
    print(f"Data Quality: {res.data_quality}")
    print(f"Explanation: {res.explanation}")
    print("Requirement Analysis:")
    for req in res.requirement_analysis:
        print(f"  - {req.normalized_requirement} | {req.status} | {req.importance}")
        print(f"    {req.explanation}")

if __name__ == '__main__':
    asyncio.run(run_smoke_test())
