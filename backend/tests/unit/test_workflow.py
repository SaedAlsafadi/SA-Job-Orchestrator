import pytest
import json
from unittest.mock import AsyncMock, patch

from app.services.eligibility import evaluate_eligibility, EligibilityResult
from app.models.job import Job
from app.schemas.candidate_profile import CandidateProfileSchema, Identity, WorkAuthorization, Location
from app.core.llm.prompts.resume_tailor import TailoredResumeData

def test_eligibility_saudi_national():
    candidate = CandidateProfileSchema(
        work_authorization=WorkAuthorization(nationality="Egyptian")
    )
    job = Job(
        title="Software Engineer",
        company="Aramco",
        url="http://test",
        gcc_eligibility={"saudi_national_only": True}
    )
    
    result = evaluate_eligibility(candidate, job)
    assert not result.is_eligible
    assert result.status == "FAIL"
    assert "Saudi nationality" in result.reasons[0]

def test_eligibility_pass():
    candidate = CandidateProfileSchema(
        work_authorization=WorkAuthorization(nationality="Saudi")
    )
    job = Job(
        title="Software Engineer",
        company="Aramco",
        url="http://test",
        gcc_eligibility={"saudi_national_only": True}
    )
    
    result = evaluate_eligibility(candidate, job)
    assert result.is_eligible
    assert result.status == "PASS"

def test_eligibility_iqama_required():
    candidate = CandidateProfileSchema(
        work_authorization=WorkAuthorization(nationality="Indian", iqama_transferable=False),
        location=Location(country="Saudi Arabia")
    )
    job = Job(
        title="Software Engineer",
        company="STC",
        url="http://test",
        country="Saudi Arabia",
        gcc_eligibility={"iqama_transferable_required": True}
    )
    
    result = evaluate_eligibility(candidate, job)
    assert not result.is_eligible
    assert result.status == "FAIL"

@pytest.mark.asyncio
async def test_candidate_job_matcher_anti_hallucination():
    # Setup LLM Mock
    mock_llm_client = AsyncMock()
    # Mock returning hallucinated evidence_id
    from app.services.matching import LLMMatchResult, MatchEvidence
    mock_llm_client.complete_with_structured_output.return_value = LLMMatchResult(
        score=90,
        strengths=[
            MatchEvidence(evidence_id="fake-id-123", description="Hallucinated skill")
        ],
        gaps=[],
        critical_gaps=[],
        recommendation="apply"
    )
    
    from app.services.matching import CandidateJobMatcher
    matcher = CandidateJobMatcher(mock_llm_client)
    
    candidate = CandidateProfileSchema()
    job = Job(title="Test Job", company="Test", url="url", gcc_eligibility={})
    
    result = await matcher.match_candidate(candidate, job)
    
    # Fake ID should be stripped
    assert len(result.strengths) == 0
