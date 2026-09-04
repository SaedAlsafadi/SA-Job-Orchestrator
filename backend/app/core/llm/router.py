import structlog
from enum import StrEnum
from typing import Any, TypeVar, Optional, Type
from pydantic import BaseModel

from app.core.llm.client import LLMClient
from app.config.settings import get_settings

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMTask(StrEnum):
    # LIGHT TASKS
    CLASSIFICATION = "classification"
    METADATA_EXTRACTION = "metadata_extraction"
    TEXT_CLEANUP = "text_cleanup"
    SUMMARY = "summary"
    DEDUP_ASSISTANCE = "dedup_assistance"
    SOURCE_CLASSIFICATION = "source_classification"
    DISCOVERY_PREPROCESS = "discovery_preprocess"
    MESSAGE_INTENT = "message_intent"

    # HEAVY TASKS
    MATCH_DEEP = "match_deep"
    JOB_REQUIREMENT_ANALYSIS = "job_requirement_analysis"
    MATCH_EXPLANATION = "match_explanation"
    CV_TAILOR = "cv_tailor"
    CV_REVIEW = "cv_review"
    APPLICATION_QA = "application_qa"
    ARABIC_GENERATION = "arabic_generation"
    ARABIC_REASONING = "arabic_reasoning"
    JOB_NORMALIZATION = "job_normalization"
    ROUTE_RESOLUTION = "route_resolution"
    COVER_LETTER = "cover_letter"
    APPLICATION_EMAIL = "application_email"
    APPLICATION_ANSWERS = "application_answers"


class LLMTaskRouter:
    """Routes LLM tasks to the appropriate configured model (Light vs Heavy)."""

    HEAVY_TASKS = {
        LLMTask.MATCH_DEEP,
        LLMTask.JOB_REQUIREMENT_ANALYSIS,
        LLMTask.MATCH_EXPLANATION,
        LLMTask.CV_TAILOR,
        LLMTask.CV_REVIEW,
        LLMTask.APPLICATION_QA,
        LLMTask.ARABIC_GENERATION,
        LLMTask.ARABIC_REASONING,
        LLMTask.JOB_NORMALIZATION,
        LLMTask.ROUTE_RESOLUTION,
        LLMTask.COVER_LETTER,
        LLMTask.APPLICATION_EMAIL,
        LLMTask.APPLICATION_ANSWERS,
    }

    def __init__(self, client: LLMClient):
        self.client = client
        self.settings = get_settings().llm

    def _get_model_for_task(self, task: LLMTask) -> str:
        if task in self.HEAVY_TASKS:
            return self.settings.heavy_model
        return self.settings.light_model

    def _get_purpose_for_task(self, task: LLMTask) -> str:
        # Re-use the task name as the purpose string for telemetry
        return str(task.value)

    async def complete(
        self,
        task: LLMTask,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        model_override: Optional[str] = None, # Strictly for tests/dev tooling
    ):
        model = model_override or self._get_model_for_task(task)
        purpose = self._get_purpose_for_task(task)
        
        logger.info("llm_task_router.complete", task=task.value, model=model, is_heavy=task in self.HEAVY_TASKS)
        
        # Disable fallback silently overriding the heavy task failure
        # By setting the client's internal fallback logic to empty or passing exact model
        
        return await self.client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            purpose=purpose,
        )

    async def complete_with_structured_output(
        self,
        task: LLMTask,
        prompt: str,
        output_schema: Type[T],
        system_prompt: str = "",
        model_override: Optional[str] = None,
    ) -> T:
        model = model_override or self._get_model_for_task(task)
        purpose = self._get_purpose_for_task(task)

        logger.info("llm_task_router.complete_with_structured_output", task=task.value, model=model, is_heavy=task in self.HEAVY_TASKS)

        return await self.client.complete_with_structured_output(
            prompt=prompt,
            output_schema=output_schema,
            system_prompt=system_prompt,
            model=model,
            purpose=purpose,
        )
