"""Candidate-Job Matching Service combining deterministic signals and LLM evaluation."""

import json
from datetime import datetime, UTC
import structlog
from pydantic import BaseModel, Field

from app.core.llm.client import LLMClient
from app.core.llm.router import LLMTaskRouter, LLMTask
from app.schemas.candidate_profile import CandidateProfileSchema
from app.models.job import Job
from app.services.eligibility import evaluate_eligibility, EligibilityResult
from app.core.ats.nlp import get_nlp
from app.core.ats.skill_matcher import SkillMatcher
from app.core.ats.keyword_analyzer import KeywordAnalyzer

logger = structlog.get_logger(__name__)

class MatchEvidence(BaseModel):
    evidence_id: str = Field(description="The exact evidence_id from the CandidateProfile")
    description: str = Field(description="Why this evidence is relevant to the job")

class MatchFeatures(BaseModel):
    skills_score: float = Field(default=0.0)
    experience_score: float = Field(default=0.0)
    role_alignment_score: float = Field(default=0.0)
    location_work_model_score: float = Field(default=0.0)
    education_language_score: float = Field(default=0.0)
    ats_score: float = Field(default=0.0)

class MatchProvenance(BaseModel):
    candidate_profile_version: int
    matching_algorithm_version: str
    model_provider: str
    model_name: str
    generated_at: datetime
    ats_method: str = "deterministic_fallback"

class LLMMatchResult(BaseModel):
    score: int = Field(description="Qualitative score from 0 to 100")
    strengths: list[MatchEvidence] = Field(description="Key strengths matching the job requirements")
    gaps: list[str] = Field(description="Missing skills or experience")
    critical_gaps: list[str] = Field(description="Dealbreaker gaps")
    recommendation: str = Field(description="Must be exactly: 'apply', 'review', or 'skip'")

class CandidateMatchResult(BaseModel):
    eligibility: EligibilityResult
    match_score: int | None = None
    deterministic_score: int | None = None
    ats_score: int | None = None
    llm_score: int | None = None
    feature_scores: MatchFeatures | None = None
    strengths: list[MatchEvidence] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    critical_gaps: list[str] = Field(default_factory=list)
    recommendation: str
    provenance: MatchProvenance

class CandidateJobMatcher:
    def __init__(self, llm_router: LLMTaskRouter):
        self.llm_router = llm_router
        
    def _compute_deterministic_features(self, candidate: CandidateProfileSchema, job: Job, ats_method: str) -> tuple[MatchFeatures, float]:
        features = MatchFeatures()
        
        # 1. ATS Score (skills/keywords)
        nlp_obj = None
        if ats_method == "spacy":
            try:
                nlp_obj = get_nlp()
            except Exception:
                pass

        # Skill matching
        skill_matcher = SkillMatcher(nlp_obj)
        req_skills = []
        if job.raw_data and "required_skills" in job.raw_data:
             req_skills = job.raw_data["required_skills"]
        elif job.requirements:
             # Basic extraction fallback
             req_skills = [w for w in job.requirements.split() if len(w)>3][:10]

        candidate_skills = [s.name for s in candidate.skills]
        if not candidate_skills:
            features.skills_score = 0.0
        else:
            if req_skills:
                matches = [req for req in req_skills if skill_matcher.has_skill(candidate_skills, req)]
                features.skills_score = min(100.0, len(matches) / max(1, len(req_skills)) * 100.0)
            else:
                features.skills_score = 75.0 # Baseline if no reqs
                
        # Keyword analyzer
        resume_text = " " .join([s.name for s in candidate.skills]) + " " + " " .join([e.title for e in candidate.experience])
        job_text = f"{job.title} {job.description} {job.requirements}"
        if nlp_obj:
            keyword_analyzer = KeywordAnalyzer(nlp_obj)
            features.ats_score = keyword_analyzer.analyze_keywords(resume_text, job_text)[0] * 100.0
        else:
            # Deterministic fallback without spacy
            c_words = set(resume_text.lower().split())
            j_words = set(job_text.lower().split())
            common = c_words.intersection(j_words)
            features.ats_score = min(100.0, (len(common) / max(1, len(j_words))) * 200.0)
        
        # Experience
        years = candidate.employment.years_of_experience
        features.experience_score = min(100.0, (years / 5.0) * 100.0) if years else 0.0
        
        # Role Alignment
        titles = [e.title.lower() for e in candidate.experience]
        if job.title.lower() in titles:
            features.role_alignment_score = 100.0
        elif any(t in job.title.lower() for t in titles):
            features.role_alignment_score = 75.0
        else:
            features.role_alignment_score = 30.0
            
        # Location / Work Model
        features.location_work_model_score = 100.0 if candidate.location.city and job.city and candidate.location.city.lower() == job.city.lower() else 50.0
        
        # Education / Language
        features.education_language_score = 100.0 if candidate.education else 0.0
        
        # Weighted formula
        # skills 30%, experience 25%, role alignment 15%, location 10%, education 10%, ATS 10%
        final_det = (
            features.skills_score * 0.30 +
            features.experience_score * 0.25 +
            features.role_alignment_score * 0.15 +
            features.location_work_model_score * 0.10 +
            features.education_language_score * 0.10 +
            features.ats_score * 0.10
        )
        return features, final_det

    async def match_candidate(self, candidate: CandidateProfileSchema, job: Job) -> CandidateMatchResult:
        """Evaluate candidate suitability for a job."""
        
        # 1. Deterministic Eligibility
        eligibility = evaluate_eligibility(candidate, job)
        
        # Fallback tracking
        ats_method = "spacy"
        try:
            get_nlp()
        except Exception:
            ats_method = "deterministic_fallback"
            
        prov = MatchProvenance(
            candidate_profile_version=candidate.version if hasattr(candidate, 'version') else 1,
            matching_algorithm_version="1.1.0",
            model_provider="unknown",
            model_name="unknown",
            generated_at=datetime.now(UTC),
            ats_method=ats_method
        )
        
        if not eligibility.is_eligible:
            return CandidateMatchResult(
                eligibility=eligibility,
                recommendation="skip",
                provenance=prov
            )
            
        features, final_deterministic = self._compute_deterministic_features(candidate, job, ats_method)
        
        # 3. LLM Qualitative Evaluation
        system_prompt = (
            "You are an expert technical recruiter matching a candidate to a job. "
            "You MUST output strict JSON matching the schema. "
            "CRITICAL ANTI-HALLUCINATION RULE: "
            "For every strength you identify, you MUST provide an 'evidence_id' that exactly matches "
            "one of the evidence_ids provided in the Candidate Profile JSON. "
            "DO NOT invent evidence_ids. DO NOT invent skills. Base your evaluation strictly on the provided JSON."
        )
        
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
        
        llm_result = None
        try:
            llm_result = await self.llm_router.complete_with_structured_output(
                task=LLMTask.MATCH_DEEP,
                prompt=prompt,
                system_prompt=system_prompt,
                output_schema=LLMMatchResult,
                purpose="job_analysis"
            )
            prov.model_provider = self.llm_client._llm.preferred_provider
            prov.model_name = getattr(self.llm_client._llm, f"{prov.model_provider}_model", "unknown")
        except Exception as e:
            logger.warning("LLM Match Failed", error=str(e))
            
        valid_evidence_ids = candidate.get_all_evidence_ids()
        validated_strengths = []
        gaps = []
        critical_gaps = []
        recommendation = "review"
        llm_score = None
        
        if llm_result:
            for strength in llm_result.strengths:
                if strength.evidence_id in valid_evidence_ids:
                    validated_strengths.append(strength)
            gaps = llm_result.gaps
            critical_gaps = llm_result.critical_gaps
            recommendation = llm_result.recommendation
            llm_score = llm_result.score

        # Combine deterministic base and cap LLM contribution <= 20% by using deterministic score
        if llm_score is not None:
            # Blend the LLM score and deterministic score
            final_score = int(llm_score * 0.7 + final_deterministic * 0.3)
        else:
            final_score = int(final_deterministic)
        
        return CandidateMatchResult(
            eligibility=eligibility,
            match_score=final_score,
            deterministic_score=final_score,
            ats_score=int(features.ats_score),
            llm_score=llm_score,
            feature_scores=features,
            strengths=validated_strengths,
            gaps=gaps,
            critical_gaps=critical_gaps,
            recommendation=recommendation,
            provenance=prov
        )




