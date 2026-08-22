import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, UTC

from app.services.matching import CandidateJobMatcher, CandidateMatchResult, LLMMatchResult, MatchEvidence
from app.schemas.candidate_profile import CandidateProfileSchema, SkillEntry
from app.models.job import Job

# --- Fixtures ---

@pytest.fixture
def base_candidate():
    return CandidateProfileSchema(
        identity={'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com', 'phone': ''},
        location={'country': 'Saudi Arabia', 'city': 'Riyadh', 'willing_to_relocate': False},
        work_authorization={'nationality': 'Saudi', 'iqama_transferable': False},
        employment={'years_of_experience': 5, 'current_company': 'Tech', 'current_title': 'Software Engineer'},
        experience=[{
            'title': 'Software Engineer',
            'company': 'Tech',
            'location': 'Riyadh',
            'start_date': '2020',
            'end_date': 'Present',
            'description': 'Did things',
            'evidence_id': 'exp-1'
        }],
        skills=[{'name': 'Python', 'confidence': 1.0, 'source': 'resume'}],
        education=[{'degree': 'BS', 'major': 'CS', 'institution': 'KSU', 'graduation_year': '2020', 'evidence_id': 'edu-1'}]
    )

@pytest.fixture
def base_job():
    return Job(
        title='Software Engineer',
        company='Acme',
        country='Saudi Arabia',
        city='Riyadh',
        description='Looking for a dev.',
        requirements='Python',
        work_model='on_site'
    )

@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    client.settings.preferred_provider = "test_provider"
    client.settings.test_provider_model = "test_model"
    client.complete_with_structured_output.return_value = LLMMatchResult(
        score=85,
        strengths=[MatchEvidence(evidence_id='exp-1', description='Great match')],
        gaps=[],
        critical_gaps=[],
        recommendation='apply'
    )
    return client

# --- Tests ---

@pytest.mark.asyncio
async def test_excellent_candidate_matching_job(base_candidate, base_job, mock_llm_client):
    matcher = CandidateJobMatcher(mock_llm_client)
    res = await matcher.match_candidate(base_candidate, base_job)
    assert res.eligibility.is_eligible is True
    assert res.match_score >= 80

@pytest.mark.asyncio
async def test_weak_candidate_poor_job(base_candidate, base_job, mock_llm_client):
    base_candidate.skills = []
    base_candidate.experience[0].title = "Chef"
    base_job.title = "Data Scientist"
    base_job.requirements = "R Pandas SQL"
    
    matcher = CandidateJobMatcher(mock_llm_client)
    res = await matcher.match_candidate(base_candidate, base_job)
    assert res.match_score < 60

@pytest.mark.asyncio
async def test_same_candidate_add_required_skill(base_candidate, base_job, mock_llm_client):
    matcher = CandidateJobMatcher(mock_llm_client)
    base_job.raw_data = {"required_skills": ["Python", "Docker"]}
    
    # Run without Docker
    res1 = await matcher.match_candidate(base_candidate, base_job)
    
    # Run with Docker
    base_candidate.skills.append(SkillEntry(name='Docker', confidence=1.0, source='resume'))
    res2 = await matcher.match_candidate(base_candidate, base_job)
    
    assert res2.match_score > res1.match_score

@pytest.mark.asyncio
async def test_same_job_remove_required_skill(base_candidate, base_job, mock_llm_client):
    matcher = CandidateJobMatcher(mock_llm_client)
    base_candidate.skills = [SkillEntry(name='Python', confidence=1.0, source='resume')]
    
    base_job.raw_data = {"required_skills": ["Python", "Docker"]}
    res1 = await matcher.match_candidate(base_candidate, base_job)
    
    base_job.raw_data = {"required_skills": ["Python"]}
    res2 = await matcher.match_candidate(base_candidate, base_job)
    
    assert res2.match_score > res1.match_score

@pytest.mark.asyncio
async def test_saudi_only_job_non_saudi_candidate(base_candidate, base_job, mock_llm_client):
    base_job.gcc_eligibility = {"saudi_national_only": True}
    base_candidate.work_authorization.nationality = "Egyptian"
    
    matcher = CandidateJobMatcher(mock_llm_client)
    res = await matcher.match_candidate(base_candidate, base_job)
    
    assert res.eligibility.is_eligible is False
    assert "Job requires Saudi nationality." in res.eligibility.reasons
    assert res.recommendation == "skip"
    mock_llm_client.complete_with_structured_output.assert_not_called()

@pytest.mark.asyncio
async def test_iqama_transferable_required(base_candidate, base_job, mock_llm_client):
    base_job.gcc_eligibility = {"iqama_transferable_required": True}
    base_candidate.work_authorization.nationality = "Egyptian"
    base_candidate.work_authorization.iqama_transferable = False
    
    matcher = CandidateJobMatcher(mock_llm_client)
    res = await matcher.match_candidate(base_candidate, base_job)
    
    assert res.eligibility.is_eligible is False
    assert "Job requires a transferable Iqama." in res.eligibility.reasons

@pytest.mark.asyncio
async def test_fake_evidence_id_rejected(base_candidate, base_job, mock_llm_client):
    mock_llm_client.complete_with_structured_output.return_value.strengths.append(
        MatchEvidence(evidence_id='fake-999', description='hallucination')
    )
    matcher = CandidateJobMatcher(mock_llm_client)
    res = await matcher.match_candidate(base_candidate, base_job)
    
    assert len(res.strengths) == 1
    assert res.strengths[0].evidence_id == 'exp-1'

@pytest.mark.asyncio
async def test_llm_unavailable(base_candidate, base_job, mock_llm_client):
    mock_llm_client.complete_with_structured_output.side_effect = Exception("OpenRouter down")
    matcher = CandidateJobMatcher(mock_llm_client)
    res = await matcher.match_candidate(base_candidate, base_job)
    
    assert res.match_score > 0
    assert res.recommendation == "review"
    assert res.llm_score is None

@pytest.mark.asyncio
async def test_two_different_jobs(base_candidate, base_job, mock_llm_client):
    matcher = CandidateJobMatcher(mock_llm_client)
    res1 = await matcher.match_candidate(base_candidate, base_job)
    
    job2 = Job(title='Doctor', company='Clinic', description='', work_model='on_site')
    res2 = await matcher.match_candidate(base_candidate, job2)
    
    assert res1.match_score != res2.match_score

@pytest.mark.asyncio
async def test_deterministic_score_stability(base_candidate, base_job, mock_llm_client):
    matcher = CandidateJobMatcher(mock_llm_client)
    res1 = await matcher.match_candidate(base_candidate, base_job)
    res2 = await matcher.match_candidate(base_candidate, base_job)
    assert res1.deterministic_score == res2.deterministic_score

@pytest.mark.asyncio
async def test_spacy_fallback_scoring(base_candidate, base_job, mock_llm_client):
    matcher = CandidateJobMatcher(mock_llm_client)
    with patch('app.services.matching.get_nlp', side_effect=Exception("No spacy")):
        res = await matcher.match_candidate(base_candidate, base_job)
        assert res.provenance.ats_method == "deterministic_fallback"

@pytest.mark.asyncio
async def test_eligibility_result_separation(base_candidate, base_job, mock_llm_client):
    matcher = CandidateJobMatcher(mock_llm_client)
    res = await matcher.match_candidate(base_candidate, base_job)
    assert res.eligibility.is_eligible is True
    assert res.eligibility.status == "WARNING"

@pytest.mark.asyncio
async def test_provenance_fields(base_candidate, base_job, mock_llm_client):
    matcher = CandidateJobMatcher(mock_llm_client)
    res = await matcher.match_candidate(base_candidate, base_job)
    assert res.provenance.matching_algorithm_version == "1.1.0"
    assert res.provenance.model_provider == "test_provider"
    assert res.provenance.model_name == "test_model"



