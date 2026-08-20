"""Deterministic eligibility engine for matching candidate profiles to job requirements."""

from pydantic import BaseModel, Field

from app.schemas.candidate_profile import CandidateProfileSchema
from app.models.job import Job

class EligibilityResult(BaseModel):
    is_eligible: bool
    status: str = Field(description="'PASS', 'WARNING', or 'FAIL'")
    reasons: list[str] = Field(default_factory=list)

def evaluate_eligibility(candidate: CandidateProfileSchema, job: Job) -> EligibilityResult:
    """Evaluate hard requirements deterministically."""
    reasons = []
    status = "PASS"
    
    # Extract GCC eligibility from job (defaulting to empty if not set)
    gcc_reqs = job.gcc_eligibility or {}
    
    # 1. Nationality checks
    if gcc_reqs.get("saudi_national_only") and candidate.work_authorization.nationality.lower() != "saudi":
        reasons.append("Job requires Saudi nationality.")
        status = "FAIL"
        
    if gcc_reqs.get("gcc_national_only") and candidate.work_authorization.nationality.lower() not in ["saudi", "emirati", "qatari", "bahraini", "kuwaiti", "omani"]:
        reasons.append("Job requires GCC nationality.")
        status = "FAIL"
        
    # 2. Iqama / Residency checks (if not a national)
    requires_iqama = gcc_reqs.get("iqama_transferable_required")
    is_national = candidate.work_authorization.nationality.lower() == job.country.lower() if job.country else False
    
    if requires_iqama and not is_national:
        if not candidate.work_authorization.iqama_transferable:
            reasons.append("Job requires a transferable Iqama.")
            status = "FAIL"

    # 3. Location checks
    if job.city and candidate.location.city:
        if job.city.lower() != candidate.location.city.lower():
            if not candidate.location.willing_to_relocate and job.work_model != "remote":
                reasons.append(f"Job is in {job.city} but candidate is in {candidate.location.city} and not willing to relocate.")
                if status == "PASS":
                    status = "WARNING"
                    
    # 4. Unknown Requirements Warning
    if job.requirements and not gcc_reqs:
        # If there are unstructured requirements but no structured ones, warn that manual review is needed
        reasons.append("Job has unstructured requirements that could not be fully verified deterministically.")
        if status == "PASS":
            status = "WARNING"

    return EligibilityResult(
        is_eligible=(status != "FAIL"),
        status=status,
        reasons=reasons
    )
