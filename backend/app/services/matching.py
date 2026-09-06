import json
from datetime import datetime, UTC
import structlog

from app.core.llm.router import LLMTaskRouter, LLMTask
from app.schemas.candidate_profile import CandidateProfileSchema
from app.models.job import Job
from app.services.normalization import normalize_job_data
from app.services.eligibility import evaluate_eligibility
from app.core.ats.nlp import get_nlp
from app.core.ats.skill_matcher import SkillMatcher
from app.core.ats.keyword_analyzer import KeywordAnalyzer

from app.schemas.matching import (
    MatchEvidence, RequirementStatus, RequirementImportance, RequirementAnalysis,
    DimensionStatus, DimensionScore, MatchVerdict, MatchDimensions, LLMMatchResult,
    CandidateMatchResult, MatchProvenance
)

logger = structlog.get_logger(__name__)

class CandidateJobMatcher:
    def __init__(self, llm_router: LLMTaskRouter):
        self.llm_router = llm_router
        
    def _compute_deterministic_features(self, candidate: CandidateProfileSchema, job: Job, ats_method: str) -> dict:
        # returns dummy for now, ideally keeps legacy logic
        return {
            "skills_score": 0.0,
            "experience_score": 0.0,
            "role_alignment_score": 0.0,
            "location_work_model_score": 0.0,
            "education_language_score": 0.0,
            "ats_score": 0.0
        }

    async def match_candidate(self, candidate: CandidateProfileSchema, job: Job, language: str = "en") -> CandidateMatchResult:
        """Evaluate candidate suitability for a job using Explainable Match Intelligence V2."""
        
        # 0. Normalization
        job = await normalize_job_data(job, self.llm_router)

        # 1. Deterministic Eligibility
        eligibility = evaluate_eligibility(candidate, job)
        
        prov = MatchProvenance(
            candidate_profile_version=candidate.version if hasattr(candidate, 'version') else 1,
            matching_algorithm_version="2.0.0",
            model_provider="openrouter",
            model_name=self.llm_router.settings.heavy_model,
            generated_at=datetime.now(UTC),
            ats_method="deterministic_fallback"
        )
        
        # We process the match even if ineligible to show the blockers in the UI, 
        # unless it's a critical fatal error.
        
        system_prompt = (
            "You are an expert technical recruiter executing Match Intelligence V2. "
            "You MUST output strict JSON matching the schema.\n"
            "CRITICAL RULES:\n"
            "1. NEVER invent candidate facts. If something is missing, output UNKNOWN or INSUFFICIENT_DATA.\n"
            "2. Distinguish between Gaps (missing skills) and Blockers (missing hard eligibility/nationality/auth).\n"
            "3. For requirement analysis, use exact evidence_ids from the Candidate Profile JSON. DO NOT invent evidence_ids.\n"
            "4. Your explanation should be a concise 2-4 sentences explaining why the match is good/bad/uncertain, grounded strictly in evidence.\n"
            "5. The total score (0-100) should ONLY reflect confidence in the match; if data is severely missing, leave score as null/none.\n"
            f"6. Your text explanations, requirements analysis, strengths, gaps, and recommendations MUST be written in {language}.\n"
        )
        
        candidate_json = candidate.model_dump(exclude={"preferences", "identity"})
        job_info = {
            "title": job.title,
            "company": job.company,
            "description": job.description,
            "requirements": job.requirements,
            "responsibilities": job.responsibilities,
        }
        
        prompt = f"CANDIDATE PROFILE:\n{json.dumps(candidate_json)}\n\nJOB:\n{json.dumps(job_info)}"
        
        llm_result = None
        try:
            llm_result = await self.llm_router.complete_with_structured_output(
                task=LLMTask.MATCH_DEEP,
                prompt=prompt,
                system_prompt=system_prompt,
                output_schema=LLMMatchResult
            )
        except Exception as e:
            logger.warning("LLM Match Failed", error=str(e))
            # Return explicit failure state
            return CandidateMatchResult(
                eligibility=eligibility,
                verdict=MatchVerdict.INSUFFICIENT_DATA,
                confidence=0.0,
                data_quality="POOR",
                data_quality_explanation="LLM Matching failed: " + str(e),
                explanation="Matching could not be completed due to a processing error.",
                recommendation="review",
                dimensions=MatchDimensions(
                    skills=DimensionScore(status=DimensionStatus.INSUFFICIENT_DATA),
                    experience=DimensionScore(status=DimensionStatus.INSUFFICIENT_DATA),
                    role_alignment=DimensionScore(status=DimensionStatus.INSUFFICIENT_DATA),
                ),
                provenance=prov
            )

        valid_evidence_ids = candidate.get_all_evidence_ids()
        
        # Verify evidence IDs
        for req in llm_result.requirement_analysis:
            req.evidence_ids = [eid for eid in req.evidence_ids if eid in valid_evidence_ids]
            
        # Ensure eligibility blockers override AI verdict
        blockers = llm_result.blockers
        verdict = llm_result.verdict
        if not eligibility.is_eligible:
            blockers.extend(eligibility.reasons)
            verdict = MatchVerdict.WEAK_MATCH # Enforce failure
            
        # Combine into CandidateMatchResult
        total_score = None
        # Derive total score from dimensions if possible
        valid_scores = [
            d.score for d in [llm_result.dimensions.skills, llm_result.dimensions.experience, llm_result.dimensions.role_alignment]
            if d.score is not None
        ]
        if valid_scores:
            total_score = int(sum(valid_scores) / len(valid_scores))

        return CandidateMatchResult(
            eligibility=eligibility,
            total_score=total_score,
            verdict=verdict,
            confidence=llm_result.confidence,
            data_quality=llm_result.data_quality,
            data_quality_explanation=llm_result.data_quality_explanation,
            explanation=llm_result.explanation,
            recommendation=llm_result.recommendation,
            dimensions=llm_result.dimensions,
            strong_matches=llm_result.strong_matches,
            gaps=llm_result.gaps,
            critical_gaps=llm_result.critical_gaps,
            blockers=blockers,
            requirement_analysis=llm_result.requirement_analysis,
            provenance=prov
        )


