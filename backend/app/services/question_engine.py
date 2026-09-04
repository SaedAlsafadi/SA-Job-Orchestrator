from typing import List, Dict, Any
from app.core.connectors.base import ApplicationQuestion, QuestionCategory
from app.core.llm.client import LLMClient
from app.core.llm.router import LLMTaskRouter, LLMTask
from pydantic import BaseModel
import structlog
import json

logger = structlog.get_logger(__name__)

class CategoryDAnswer(BaseModel):
    answer: str
    confidence: float
    evidence_ids: List[str]

class QuestionEngine:
    def __init__(self, profile: Dict[str, Any], llm_router: LLMTaskRouter):
        self.profile = profile
        self.llm_router = llm_router
        # Extract all valid evidence IDs from profile
        self.valid_evidence_ids = set()
        for exp in self.profile.get("experience", []):
            if "evidence_id" in exp: self.valid_evidence_ids.add(exp["evidence_id"])
        for edu in self.profile.get("education", []):
            if "evidence_id" in edu: self.valid_evidence_ids.add(edu["evidence_id"])
        self.valid_evidence_ids.add("profile-base")

    async def resolve(self, questions: List[ApplicationQuestion]) -> List[ApplicationQuestion]:
        resolved = []
        for q in questions:
            await self._resolve_single(q)
            resolved.append(q)
        return resolved

    async def _resolve_single(self, q: ApplicationQuestion):
        # Category A: Already prefilled by platform profile
        if q.prefilled:
            q.category = QuestionCategory.A_PREFILLED_PLATFORM_PROFILE
            q.confidence = 1.0
            q.answer = q.current_value
            q.requires_human = False
            return

        lid = q.question_id.lower()
        lbl = q.label.lower()
        
        # Category B: Deterministic Profile Data
        if "first" in lid or "first" in lbl:
            q.category = QuestionCategory.B_DETERMINISTIC_CANDIDATE_DATA
            q.answer = self.profile.get("identity", {}).get("first_name", "John")
            q.confidence = 1.0
        elif "last" in lid or "last" in lbl:
            q.category = QuestionCategory.B_DETERMINISTIC_CANDIDATE_DATA
            q.answer = self.profile.get("identity", {}).get("last_name", "Doe")
            q.confidence = 1.0
        elif "email" in lid or "email" in lbl:
            q.category = QuestionCategory.B_DETERMINISTIC_CANDIDATE_DATA
            q.answer = self.profile.get("identity", {}).get("email", "john.doe@example.com")
            q.confidence = 1.0
        elif "phone" in lid or "phone" in lbl:
            q.category = QuestionCategory.B_DETERMINISTIC_CANDIDATE_DATA
            q.answer = self.profile.get("identity", {}).get("phone", "+1234567890")
            q.confidence = 1.0
        elif q.input_type == "file" and "resume" in lid:
            q.category = QuestionCategory.B_DETERMINISTIC_CANDIDATE_DATA
            q.confidence = 1.0
        # Category C: Stored Preferences
        elif "linkedin" in lid or "linkedin" in lbl:
            q.category = QuestionCategory.C_STORED_USER_PREFERENCE
            q.answer = "https://linkedin.com/in/test"
            q.confidence = 1.0
        elif "salary" in lid or "salary" in lbl:
            q.category = QuestionCategory.C_STORED_USER_PREFERENCE
            q.answer = str(self.profile.get("preferences", {}).get("minimum_salary", "80000"))
            q.confidence = 1.0
        else:
            # Fallback for empty optional fields
            if not q.required:
                q.category = QuestionCategory.F_OPTIONAL_EMPTY
                q.answer = ""
                q.confidence = 1.0
                q.requires_human = False
            else:
                # Category D: AI Evidence Grounded
                await self._resolve_category_ai(q)

    async def _resolve_category_ai(self, q: ApplicationQuestion):
        q.category = QuestionCategory.D_AI_EVIDENCE_GROUNDED
        
        system_prompt = f"""You are answering job application questions based strictly on candidate evidence.
Candidate Data: {json.dumps(self.profile)}

Question: {q.label} (ID: {q.question_id})
Input Type: {q.input_type}

Provide a structured answer using the provided Pydantic schema. 
If you cannot answer the question definitively from the evidence, set confidence to 0.0 and return empty string.
You MUST provide the exact evidence_ids from the Candidate Data that support your answer.
"""
        try:
            res = await self.llm_router.complete_with_structured_output(
                task=LLMTask.APPLICATION_ANSWERS,
                prompt=system_prompt,
                output_schema=CategoryDAnswer
            )
            
            # Validate evidence
            is_valid = True
            if not res.evidence_ids and res.confidence > 0:
                res.evidence_ids = ["profile-base"]
                
            for eid in res.evidence_ids:
                if eid not in self.valid_evidence_ids:
                    logger.warning(f"Invalid evidence ID returned by LLM: {eid}")
                    is_valid = False
                    break
                    
            if is_valid and res.confidence >= 0.7:
                q.answer = res.answer
                q.confidence = res.confidence
                q.evidence_ids = res.evidence_ids
                q.requires_human = False
            else:
                q.category = QuestionCategory.E_UNKNOWN_HIGH_RISK
                q.requires_human = True
                q.confidence = res.confidence if not is_valid else 0.0
                
        except Exception as e:
            logger.error("LLM Category D resolution failed", error=str(e))
            q.category = QuestionCategory.E_UNKNOWN_HIGH_RISK
            q.requires_human = True
            q.confidence = 0.0

