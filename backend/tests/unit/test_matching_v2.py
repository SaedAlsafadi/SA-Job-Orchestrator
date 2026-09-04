import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.matching import CandidateJobMatcher
from app.schemas.matching import (
    MatchVerdict, DimensionScore, MatchDimensions, DimensionStatus,
    LLMMatchResult, CandidateMatchResult, RequirementAnalysis,
    RequirementStatus, RequirementImportance
)
from app.core.llm.router import LLMTaskRouter
from app.schemas.candidate_profile import CandidateProfileSchema
from app.models.job import Job

@pytest.fixture
def mock_router():
    router = MagicMock(spec=LLMTaskRouter)
    router.settings = MagicMock()
    router.settings.heavy_model = "test-model"
    router.complete_with_structured_output = AsyncMock()
    return router

@pytest.fixture
def dummy_candidate():
    return CandidateProfileSchema(
        user_id="user1",
        version=1,
        headline="Software Engineer",
        summary="I write code",
        skills=[],
        experience=[],
        education=[],
        languages=[],
        preferences={"remote": True}
    )

@pytest.fixture
def dummy_job():
    return Job(
        title="Software Engineer",
        company="Tech Inc",
        description="Write code.",
        requirements="Python",
        responsibilities="Code",
        is_normalized=True
    )

@pytest.mark.asyncio
async def test_missing_data_not_zero(mock_router, dummy_candidate, dummy_job):
    matcher = CandidateJobMatcher(mock_router)
    
    mock_router.complete_with_structured_output.return_value = LLMMatchResult(
        verdict=MatchVerdict.INSUFFICIENT_DATA,
        confidence=0.1,
        data_quality="LIMITED",
        data_quality_explanation="Missing info",
        explanation="Not enough info",
        recommendation="review",
        strong_matches=[],
        gaps=[],
        critical_gaps=[],
        blockers=[],
        requirement_analysis=[],
        dimensions=MatchDimensions(
            skills=DimensionScore(status=DimensionStatus.INSUFFICIENT_DATA, score=None),
            experience=DimensionScore(status=DimensionStatus.INSUFFICIENT_DATA, score=None),
            role_alignment=DimensionScore(status=DimensionStatus.INSUFFICIENT_DATA, score=None)
        )
    )
    
    res = await matcher.match_candidate(dummy_candidate, dummy_job)
    
    # Missing data should NOT equate to 0 score
    assert res.total_score is None
    assert res.verdict == MatchVerdict.INSUFFICIENT_DATA
    assert res.dimensions.skills.score is None

@pytest.mark.asyncio
async def test_llm_failure_graceful(mock_router, dummy_candidate, dummy_job):
    matcher = CandidateJobMatcher(mock_router)
    mock_router.complete_with_structured_output.side_effect = Exception("API limit")
    
    res = await matcher.match_candidate(dummy_candidate, dummy_job)
    
    assert res.total_score is None
    assert res.verdict == MatchVerdict.INSUFFICIENT_DATA
    assert res.data_quality == "POOR"

@pytest.mark.asyncio
@patch('app.services.matching.evaluate_eligibility')
async def test_eligibility_fail_overrides_llm(mock_eligibility, mock_router, dummy_candidate, dummy_job):
    # Deterministic FAIL
    from app.services.eligibility import EligibilityResult
    mock_eligibility.return_value = EligibilityResult(is_eligible=False, status="FAIL", reasons=["Not authorized"])
    matcher = CandidateJobMatcher(mock_router)
    
    mock_router.complete_with_structured_output.return_value = LLMMatchResult(
        verdict=MatchVerdict.STRONG_MATCH, # LLM hallucinated a strong match despite auth
        confidence=0.9,
        data_quality="HIGH",
        explanation="Great fit",
        recommendation="apply",
        strong_matches=[], gaps=[], critical_gaps=[], blockers=[], requirement_analysis=[],
        dimensions=MatchDimensions(
            skills=DimensionScore(status=DimensionStatus.VALID_SCORE, score=90),
            experience=DimensionScore(status=DimensionStatus.VALID_SCORE, score=90),
            role_alignment=DimensionScore(status=DimensionStatus.VALID_SCORE, score=90)
        )
    )
    
    res = await matcher.match_candidate(dummy_candidate, dummy_job)
    
    # Verdict must be downgraded
    assert res.verdict == MatchVerdict.WEAK_MATCH
    assert "Not authorized" in res.blockers


