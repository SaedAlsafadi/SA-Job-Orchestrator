import pytest
import uuid
import json
from unittest.mock import AsyncMock

from app.models.enums import TailoringStatus, ChangeType, ReviewerStatus, ReviewSeverity
from app.models.resume import Resume
from app.models.job import Job
from app.models.candidate_profile import CandidateProfile
from app.models.tailoring import CVTailoringSession, CVTailoringChange
from app.core.llm.router import LLMTaskRouter, LLMTask
from app.schemas.tailoring import CVTailorOutput, CVReviewOutput, ProposedChangeOutput, ReviewDecisionOutput
from app.schemas.matching import LLMMatchResult, MatchVerdict, MatchDimensions, DimensionScore
from app.services.tailoring import start_tailoring_session
from app.services.matching import CandidateJobMatcher
from app.schemas.candidate_profile import CandidateProfileSchema
from app.services.normalization import normalize_job_data, NormalizedJob


@pytest.fixture
def arabic_job(db_session, current_user):
    job = Job(
        user_id=current_user.id,
        id=uuid.uuid4().hex,
        platform="test",
        platform_job_id="test_job_1",
        title="مهندس برمجيات",
        company="شركة اختبار",
        description="نبحث عن مهندس برمجيات ذو خبرة في بايثون.",
        url="http://test",
    )
    db_session.add(job)
    return job

@pytest.fixture
def arabic_resume(db_session, current_user):
    resume = Resume(
        user_id=current_user.id,
        id=uuid.uuid4().hex,
        name="السيرة الذاتية",
        type="base",
        content_text=json.dumps({"skills": ["بايثون", "رياكت"], "experience": [{"title": "مطور برمجيات"}]})
    )
    db_session.add(resume)
    return resume

@pytest.fixture
def mock_router_arabic():
    router = LLMTaskRouter(client=AsyncMock())
    async def mock_complete(*args, **kwargs):
        task = kwargs.get('task')
        if task == LLMTask.JOB_NORMALIZATION:
            return NormalizedJob(
                title="Software Engineer",
                company="Test Company",
                location="Unknown",
                description="We are looking for a Software Engineer experienced in Python.",
                confidence=0.9
            )
        if task == LLMTask.MATCH_DEEP:
            return LLMMatchResult(
                verdict=MatchVerdict.STRONG_MATCH,
                confidence=0.9,
                data_quality="HIGH",
                data_quality_explanation=None,
                explanation="المرشح مناسب جداً لهذه الوظيفة لوجود خبرة في بايثون.",
                recommendation="apply",
                strong_matches=["بايثون"],
                gaps=[],
                critical_gaps=[],
                blockers=[],
                requirement_analysis=[],
                dimensions=MatchDimensions(
                    skills=DimensionScore(status="VALID_SCORE", score=90, explanation="المرشح لديه خبرة في بايثون."),
                    experience=DimensionScore(status="VALID_SCORE", score=90, explanation="خبرة ممتازة."),
                    role_alignment=DimensionScore(status="VALID_SCORE", score=90, explanation="مناسب جداً.")
                )
            )
        if task == LLMTask.CV_REVIEW:
            return CVReviewOutput(
                reviews=[
                    ReviewDecisionOutput(
                        change_id="mock",
                        severity=ReviewSeverity.SAFE,
                        reason="آمن"
                    )
                ]
            )
        if task == LLMTask.CV_TAILOR:
            return CVTailorOutput(
                changes=[
                    ProposedChangeOutput(
                        target_type="inline",
                        target_reference="skills[0]",
                        section="skills",
                        original_text="بايثون",
                        proposed_text="بايثون/جانغو",
                        change_type=ChangeType.MODIFY,
                        reason="الوظيفة تتطلب خبرة إضافية",
                        linked_requirement_ids=[],
                        linked_evidence_ids=[]
                    )
                ]
            )
        raise ValueError(f"Unhandled task: {task}")
    router.complete_with_structured_output = AsyncMock(side_effect=mock_complete)
    return router


@pytest.mark.asyncio
async def test_arabic_job_normalization(db_session, current_user, arabic_job, mock_router_arabic):
    # Test that Arabic text gets normalized to English concepts
    normalized_job = await normalize_job_data(arabic_job, mock_router_arabic)
    assert normalized_job.title == "Software Engineer"
    assert normalized_job.is_normalized == True
    # Verify we preserve original raw text
    assert "مهندس برمجيات" in normalized_job.raw_text


@pytest.mark.asyncio
async def test_arabic_matching_explanation(db_session, current_user, arabic_job, arabic_resume, mock_router_arabic):
    schema = CandidateProfileSchema(
        identity={},
        location={},
        employment={},
        work_authorization={},
        education=[],
        projects=[],
        certifications=[],
        languages=[],
        preferences={},
        skills=["بايثون", "رياكت"],
        experience=[{"title": "مطور برمجيات"}]
    )
    matcher = CandidateJobMatcher(mock_router_arabic)
    
    # Test Match (pass language)
    res = await matcher.match_candidate(schema, arabic_job, language="ar")
    
    assert res.verdict == MatchVerdict.STRONG_MATCH
    assert "المرشح مناسب جداً" in res.explanation
    
    # Verify system prompt included Arabic directive
    kwargs = mock_router_arabic.complete_with_structured_output.call_args.kwargs
    assert "MUST be written in ar" in kwargs["system_prompt"]


@pytest.mark.asyncio
async def test_arabic_cv_tailoring(db_session, current_user, arabic_job, arabic_resume, mock_router_arabic):
    await db_session.commit()
    
    # Test Tailoring
    session = await start_tailoring_session(
        db=db_session,
        user_id=current_user.id,
        job_id=arabic_job.id,
        base_resume_id=arabic_resume.id,
        router=mock_router_arabic,
        language="ar"
    )
    
    await db_session.commit()
    await db_session.refresh(session, ["changes"])
    
    assert len(session.changes) == 1
    assert session.changes[0].original_text == "بايثون"
    assert session.changes[0].proposed_text == "بايثون/جانغو"
    assert session.changes[0].reason == "الوظيفة تتطلب خبرة إضافية"
    
    # Verify system prompt
    tailor_call = next(call for call in mock_router_arabic.complete_with_structured_output.call_args_list if call.kwargs.get('task') == LLMTask.CV_TAILOR)
    kwargs = tailor_call.kwargs
    assert "MUST be written in ar" in kwargs["system_prompt"]
