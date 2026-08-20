"""Candidate-Job Matching Service combining deterministic signals and LLM evaluation."""

import json
from pydantic import BaseModel, Field

from app.core.llm.client import LLMClient
from app.schemas.candidate_profile import CandidateProfileSchema
from app.models.job import Job
from app.services.eligibility import evaluate_eligibility, EligibilityResult

class MatchEvidence(BaseModel):
    evidence_id: str = Field(description="The exact evidence_id from the CandidateProfile (e.g. exp-1234, skill-5678)")
    description: str = Field(description="Why this evidence is relevant to the job")

class LLMMatchResult(BaseModel):
    score: int = Field(description="Match score from 0 to 100")
    strengths: list[MatchEvidence] = Field(description="Key strengths matching the job requirements")
    gaps: list[str] = Field(description="Missing skills or experience")
    critical_gaps: list[str] = Field(description="Dealbreaker gaps that make the candidate unsuitable")
    recommendation: str = Field(description="Must be exactly: 'apply', 'review', or 'skip'")

class CandidateMatchResult(BaseModel):
    eligibility: EligibilityResult
    ats_score: int | None = None
    match_score: int
    strengths: list[MatchEvidence]
    gaps: list[str]
    critical_gaps: list[str]
    recommendation: str

class CandidateJobMatcher:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def match_candidate(self, candidate: CandidateProfileSchema, job: Job) -> CandidateMatchResult:
        """Evaluate candidate suitability for a job."""
        
        # 1. Deterministic Eligibility
        eligibility = evaluate_eligibility(candidate, job)
        
        # 2. Existing ATS signals (Mocked for now as we transition architecture)
        ats_score = 85 # TODO: Hook into existing ATS scorer if needed for textual compatibility
        
        # 3. Gemini Qualitative Evaluation
        system_prompt = (
            "You are an expert technical recruiter matching a candidate to a job. "
            "You MUST output strict JSON matching the schema. "
            "CRITICAL ANTI-HALLUCINATION RULE: "
            "For every strength you identify, you MUST provide an 'evidence_id' that exactly matches "
            "one of the evidence_ids provided in the Candidate Profile JSON. "
            "DO NOT invent evidence_ids. DO NOT invent skills. Base your evaluation strictly on the provided JSON."
        )
        
        # Strip out non-essential info to save tokens and focus the LLM
        candidate_json = candidate.model_dump(exclude={"preferences", "identity"})
        
        job_info = {
            "title": job.title,
            "company": job.company,
            "description": job.description,
            "requirements": job.requirements,
            "responsibilities": job.responsibilities,
            "seniority": job.seniority,
            "work_model": job.work_model
        }

        prompt = f"CANDIDATE PROFILE:\n{json.dumps(candidate_json)}\n\nJOB:\n{json.dumps(job_info)}"
        
        llm_result = await self.llm_client.complete_with_structured_output(
            prompt=prompt,
            system_prompt=system_prompt,
            output_schema=LLMMatchResult,
            purpose="job_analysis"
        )
        
        # 4. Anti-hallucination validation
        valid_evidence_ids = candidate.get_all_evidence_ids()
        validated_strengths = []
        
        for strength in llm_result.strengths:
            if strength.evidence_id in valid_evidence_ids:
                validated_strengths.append(strength)
            else:
                # Discard hallucinated evidence IDs
                pass
                
        # If the candidate hard-failed eligibility, cap the match score and recommend skip
        final_score = llm_result.score
        recommendation = llm_result.recommendation
        
        if not eligibility.is_eligible:
            final_score = min(final_score, 40)
            recommendation = "skip"

        return CandidateMatchResult(
            eligibility=eligibility,
            ats_score=ats_score,
            match_score=final_score,
            strengths=validated_strengths,
            gaps=llm_result.gaps,
            critical_gaps=llm_result.critical_gaps,
            recommendation=recommendation
        )
