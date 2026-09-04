import structlog
from app.models.job import Job
from app.core.llm.router import LLMTaskRouter, LLMTask
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

class NormalizedJob(BaseModel):
    title: str = Field(description="Normalized job title")
    company: str = Field(description="Normalized company name")
    location: str = Field(description="Normalized location")
    description: str = Field(description="Cleaned, normalized description prioritizing the actual employer content")
    confidence: float = Field(description="Extraction confidence 0.0 to 1.0")
    data_quality_flags: dict = Field(description="Dictionary of flags like {'boilerplate_detected': True}", default_factory=dict)

async def normalize_job_data(job: Job, router: LLMTaskRouter) -> Job:
    if job.is_normalized:
        return job
        
    system_prompt = (
        "You are a data quality engine. Clean this raw job posting.\n"
        "Remove aggregator boilerplate, duplicate headings, and unrelated text.\n"
        "Output strict JSON."
    )
    
    raw_text = job.raw_text or job.description
    
    try:
        res = await router.complete_with_structured_output(
            task=LLMTask.JOB_NORMALIZATION,
            prompt=f"RAW POSTING:\n{raw_text}",
            system_prompt=system_prompt,
            output_schema=NormalizedJob
        )
        
        # Save old data
        if not job.raw_text:
            job.raw_text = job.description
            
        job.title = res.title
        job.company = res.company
        job.location = res.location
        job.description = res.description
        job.extraction_confidence = res.confidence
        job.data_quality_flags = res.data_quality_flags
        job.is_normalized = True
        
    except Exception as e:
        logger.error("Normalization failed", error=str(e))
        job.extraction_confidence = 0.0
        job.data_quality_flags = {"error": str(e)}
        job.is_normalized = True # mark as processed even if failed to avoid infinite retries
        
    return job
