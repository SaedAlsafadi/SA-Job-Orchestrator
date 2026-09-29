import json
import re
from datetime import UTC, datetime

import structlog

from app.core.llm.router import LLMTask, LLMTaskRouter
from app.models.job import Job
from app.schemas.candidate_profile import CandidateProfileSchema
from app.schemas.matching import (
    CandidateMatchResult,
    DimensionScore,
    DimensionStatus,
    EvidenceType,
    LLMMatchResult,
    MatchDimensions,
    MatchEvidence,
    MatchProvenance,
    MatchVerdict,
    RequirementAnalysis,
    RequirementCategory,
    RequirementImportance,
    RequirementStatus,
)
from app.services.eligibility import evaluate_eligibility
from app.services.normalization import normalize_job_data

logger = structlog.get_logger(__name__)

_IMPORTANCE_WEIGHT = {
    RequirementImportance.CRITICAL: 4.0,
    RequirementImportance.HIGH: 3.0,
    RequirementImportance.MEDIUM: 2.0,
    RequirementImportance.LOW: 1.0,
}
_EVIDENCE_CREDIT = {
    EvidenceType.DIRECT: 1.0,
    EvidenceType.TRANSFERABLE: 0.55,
    EvidenceType.WEAK: 0.25,
    EvidenceType.NONE: 0.0,
    EvidenceType.UNKNOWN: 0.0,
}
_TRANSFERABLE_CLUSTERS = {
    "monitoring": {
        "monitor",
        "monitoring",
        "track",
        "tracking",
        "performance",
        "metrics",
    },
    "operations": {"operations", "operational", "workflow", "process", "service"},
    "reporting": {"report", "reporting", "data", "records", "metadata", "analytics"},
    "coordination": {
        "coordinate",
        "coordination",
        "stakeholder",
        "communication",
        "incident",
    },
    "automation": {"automation", "automate", "python", "script", "workflow"},
    "troubleshooting": {"troubleshoot", "technical", "support", "diagnose", "software"},
}


def _normalized_category(req: RequirementAnalysis) -> str:
    raw = f"{req.original_text} {req.normalized_requirement}".casefold()
    if any(word in raw for word in ("preferred", "nice to have", "advantage")):
        return RequirementCategory.PREFERRED.value
    if any(word in raw for word in ("ericsson", "packet core", "telecom")) or re.search(
        r"\b(?:ran|vas)\b", raw
    ):
        return RequirementCategory.DOMAIN_EXPERIENCE.value
    if any(
        word in raw
        for word in ("must", "required", "minimum", "at least", "eligib", "degree")
    ):
        return RequirementCategory.HARD_REQUIREMENT.value
    if any(
        word in raw
        for word in (
            "monitor",
            "coordinate",
            "manage",
            "support",
            "troubleshoot",
            "report",
        )
    ):
        return RequirementCategory.CORE_RESPONSIBILITY.value
    return RequirementCategory.TRANSFERABLE_COMPETENCY.value


def _candidate_evidence(candidate: CandidateProfileSchema) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for item in [
        *candidate.experience,
        *candidate.education,
        *candidate.skills,
        *candidate.projects,
        *candidate.certifications,
    ]:
        data = item.model_dump()
        evidence[item.evidence_id] = "; ".join(
            str(value)
            for key, value in data.items()
            if key != "evidence_id" and value not in (None, "", [], {})
        )[:500]
    return evidence


def _direct_skill_matches(
    req: RequirementAnalysis,
    candidate: CandidateProfileSchema,
) -> list[str]:
    """Ground explicit résumé skill names without asking the model to rediscover them."""
    requirement = _requirement_key(f"{req.original_text} {req.normalized_requirement}")
    requirement = requirement.replace("restful", "rest").replace(
        "javascript es6", "javascript"
    )
    matches: list[str] = []
    for skill in candidate.skills:
        name = (skill.name or "").strip()
        tokens = _requirement_key(name).split()
        if (
            not tokens
            or len(tokens) > 4
            or tokens[0] in {"and", "manage", "automate", "generate", "collected"}
            or tokens == ["programming"]
        ):
            continue
        normalized = " ".join(tokens).replace("restful", "rest")
        if len(normalized) >= 3 and normalized in requirement:
            matches.append(skill.evidence_id)
    return matches[:3]


def _transferable_matches(
    req: RequirementAnalysis, evidence: dict[str, str]
) -> list[str]:
    req_words = set(
        re.findall(
            r"[a-z]+", f"{req.original_text} {req.normalized_requirement}".casefold()
        )
    )
    relevant_clusters = [
        terms for terms in _TRANSFERABLE_CLUSTERS.values() if req_words & terms
    ]
    if not relevant_clusters:
        return []
    matches: list[str] = []
    for evidence_id, description in evidence.items():
        words = set(re.findall(r"[a-z]+", description.casefold()))
        if any(words & terms for terms in relevant_clusters):
            matches.append(evidence_id)
    return matches[:3]


def _requirement_key(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _default_importance(category: str, text: str) -> RequirementImportance:
    lowered = text.casefold()
    if category == RequirementCategory.PREFERRED.value:
        return RequirementImportance.LOW
    if category == RequirementCategory.HARD_REQUIREMENT.value:
        return RequirementImportance.CRITICAL
    if category == RequirementCategory.DOMAIN_EXPERIENCE.value:
        return (
            RequirementImportance.CRITICAL
            if any(
                word in lowered for word in ("must", "required", "minimum", "at least")
            )
            else RequirementImportance.HIGH
        )
    if category == RequirementCategory.CORE_RESPONSIBILITY.value:
        return RequirementImportance.HIGH
    return RequirementImportance.MEDIUM


def _ensure_requirement_coverage(
    requirements: list[RequirementAnalysis],
    source_requirements: list[str] | str | None,
) -> None:
    """Conservatively add any source requirement omitted by the model."""
    # A wholly missing analysis is an insufficient-data result, not a numeric zero.
    if not requirements:
        return
    represented = {_requirement_key(item.original_text) for item in requirements} | {
        _requirement_key(item.normalized_requirement) for item in requirements
    }
    if isinstance(source_requirements, str):
        source_items = [
            re.sub(r"^[\\\-*•\s]+", "", line).strip()
            for line in source_requirements.splitlines()
            if line.strip()
        ]
    else:
        source_items = source_requirements or []
    for index, original in enumerate(source_items, start=1):
        if not original or _requirement_key(original) in represented:
            continue
        draft = RequirementAnalysis(
            requirement_id=f"source-req-{index}",
            original_text=original,
            normalized_requirement=original,
            category=RequirementCategory.TRANSFERABLE_COMPETENCY.value,
            importance=RequirementImportance.MEDIUM,
            status=RequirementStatus.GAP,
            evidence_type=EvidenceType.NONE,
            explanation=(
                "No model-classified candidate evidence was returned for this source "
                "requirement; it is scored conservatively as unsupported."
            ),
        )
        draft.category = _normalized_category(draft)
        draft.importance = _default_importance(draft.category, original)
        requirements.append(draft)
        represented.add(_requirement_key(original))


def score_requirement_analysis(requirements: list[RequirementAnalysis]) -> int | None:
    """Assign deterministic evidence contributions and return their normalized score."""
    if not requirements:
        return None
    total_weight = sum(_IMPORTANCE_WEIGHT[req.importance] for req in requirements)
    earned = 0.0
    for req in requirements:
        weight = _IMPORTANCE_WEIGHT[req.importance]
        req.max_contribution = round(weight / total_weight * 100, 2)
        req.contribution = round(
            req.max_contribution * _EVIDENCE_CREDIT[req.evidence_type], 2
        )
        earned += req.contribution
    return max(0, min(100, round(earned)))


def finalize_requirement_analysis(
    requirements: list[RequirementAnalysis],
    candidate: CandidateProfileSchema,
    source_requirements: list[str] | str | None,
) -> int | None:
    """Validate evidence, fill omissions, apply transferability, and score."""
    _ensure_requirement_coverage(requirements, source_requirements)
    valid_evidence_ids = candidate.get_all_evidence_ids()
    evidence_map = _candidate_evidence(candidate)
    for req in requirements:
        req.evidence_ids = [
            eid for eid in req.evidence_ids if eid in valid_evidence_ids
        ]
        req.category = _normalized_category(req)
        direct_skill_ids = _direct_skill_matches(req, candidate)
        if direct_skill_ids:
            req.evidence_ids = direct_skill_ids
            requires_depth = any(
                phrase in f"{req.original_text} {req.normalized_requirement}".casefold()
                for phrase in ("experience", "proficiency", "strong command", "years")
            )
            skills_by_id = {skill.evidence_id: skill for skill in candidate.skills}
            has_depth_evidence = any(
                (skills_by_id[eid].years or 0) > 0 or bool(skills_by_id[eid].evidence)
                for eid in direct_skill_ids
            )
            if requires_depth and not has_depth_evidence:
                req.status = RequirementStatus.PARTIAL
                req.evidence_type = EvidenceType.WEAK
                req.explanation = (
                    "The canonical profile lists the relevant skill, but does not "
                    "verify the requested depth or years of experience."
                )
            else:
                req.status = RequirementStatus.MATCH
                req.evidence_type = EvidenceType.DIRECT
                req.explanation = (
                    "Canonical candidate skills directly support this requirement."
                )
        elif req.evidence_ids:
            if req.evidence_type in {EvidenceType.NONE, EvidenceType.UNKNOWN}:
                req.evidence_type = (
                    EvidenceType.DIRECT
                    if req.status == RequirementStatus.MATCH
                    else (
                        EvidenceType.TRANSFERABLE
                        if req.status == RequirementStatus.PARTIAL
                        else EvidenceType.WEAK
                    )
                )
        elif req.category in {
            RequirementCategory.CORE_RESPONSIBILITY.value,
            RequirementCategory.TRANSFERABLE_COMPETENCY.value,
        }:
            transferable_ids = _transferable_matches(req, evidence_map)
            if transferable_ids:
                req.evidence_ids = transferable_ids
                req.status = RequirementStatus.PARTIAL
                req.evidence_type = EvidenceType.TRANSFERABLE
                req.explanation = (
                    "Transferable evidence supports part of this responsibility; "
                    "it does not establish direct domain experience."
                )
            else:
                req.evidence_type = EvidenceType.NONE
        else:
            req.evidence_type = EvidenceType.NONE
        req.candidate_evidence = [
            MatchEvidence(evidence_id=eid, description=evidence_map[eid])
            for eid in req.evidence_ids
            if eid in evidence_map
        ]
    return score_requirement_analysis(requirements)


class CandidateJobMatcher:
    def __init__(self, llm_router: LLMTaskRouter) -> None:
        self.llm_router = llm_router

    def _compute_deterministic_features(
        self, candidate: CandidateProfileSchema, job: Job, ats_method: str
    ) -> dict:
        # returns dummy for now, ideally keeps legacy logic
        return {
            "skills_score": 0.0,
            "experience_score": 0.0,
            "role_alignment_score": 0.0,
            "location_work_model_score": 0.0,
            "education_language_score": 0.0,
            "ats_score": 0.0,
        }

    async def match_candidate(
        self, candidate: CandidateProfileSchema, job: Job, language: str = "en"
    ) -> CandidateMatchResult:
        """Evaluate candidate suitability for a job using Explainable Match Intelligence V2."""

        # 0. Normalization
        job = await normalize_job_data(job, self.llm_router)

        # 1. Deterministic Eligibility
        eligibility = evaluate_eligibility(candidate, job)

        prov = MatchProvenance(
            candidate_profile_version=(
                candidate.version if hasattr(candidate, "version") else 1
            ),
            matching_algorithm_version="2.1.0",
            model_provider="openrouter",
            model_name=self.llm_router.settings.heavy_model,
            generated_at=datetime.now(UTC),
            ats_method="deterministic_fallback",
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
            "6. Classify every requirement as HARD_REQUIREMENT, CORE_RESPONSIBILITY, DOMAIN_EXPERIENCE, PREFERRED, or TRANSFERABLE_COMPETENCY.\n"
            "7. Label evidence as DIRECT, TRANSFERABLE, WEAK, or NONE. TRANSFERABLE evidence earns partial credit but must never be described as direct domain experience.\n"
            f"8. Your text explanations, requirements analysis, strengths, gaps, and recommendations MUST be written in {language}.\n"
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
                output_schema=LLMMatchResult,
                # Requirement-level evidence can be a fairly large JSON object.
                # The previous 4k ceiling truncated a real 14-requirement result.
                max_tokens=8192,
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
                    role_alignment=DimensionScore(
                        status=DimensionStatus.INSUFFICIENT_DATA
                    ),
                ),
                provenance=prov,
            )

        # Ensure eligibility blockers override AI verdict
        blockers = llm_result.blockers
        verdict = llm_result.verdict
        if not eligibility.is_eligible:
            blockers.extend(eligibility.reasons)
            verdict = MatchVerdict.WEAK_MATCH  # Enforce failure

        # Combine into CandidateMatchResult
        total_score = finalize_requirement_analysis(
            llm_result.requirement_analysis,
            candidate,
            job.requirements,
        )
        # Legacy/provider results with no requirement breakdown retain the dimension
        # fallback, but explainable per-requirement scoring is authoritative otherwise.
        if total_score is None:
            valid_scores = [
                d.score
                for d in [
                    llm_result.dimensions.skills,
                    llm_result.dimensions.experience,
                    llm_result.dimensions.role_alignment,
                ]
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
            provenance=prov,
        )
