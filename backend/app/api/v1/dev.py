"""Development-only endpoints for testing and diagnostics."""

import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config.settings import get_settings
from app.core.llm.client import LLMClient
from app.api.deps import require_superuser

router = APIRouter()

class LLMHealthResponse(BaseModel):
    provider: str
    model: str
    success: bool
    latency_ms: float
    error_message: str | None = None

@router.get("/llm-health", response_model=LLMHealthResponse)
async def llm_health() -> LLMHealthResponse:
    """Development-only endpoint to verify LLM connectivity and configuration."""
    settings = get_settings()
    # Check if preferred provider key exists
    provider_key = f"{settings.llm.preferred_provider}_api_key"
    if not getattr(settings.llm, provider_key, None) or not getattr(settings.llm, provider_key).get_secret_value():
        return LLMHealthResponse(
            provider=settings.llm.preferred_provider,
            model=settings.llm.default_model,
            success=False,
            latency_ms=0.0,
            error_message=f"{provider_key.upper()} is not configured in .env"
        )
    
    client = LLMClient()
    
    try:
        start_time = time.perf_counter()
        # Minimal request
        response = await client.complete(
            prompt="Reply with the exact word 'OK'",
            model=settings.llm.default_model,
            temperature=0.0,
            max_tokens=10
        )
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        success = "OK" in response.content.strip()
        
        return LLMHealthResponse(
            provider=response.provider,
            model=response.model,
            success=success,
            latency_ms=latency_ms,
            error_message=None if success else f"Unexpected response: {response.content}"
        )
    except Exception as exc:
        return LLMHealthResponse(
            provider=settings.llm.preferred_provider,
            model=settings.llm.default_model,
            success=False,
            latency_ms=0.0,
            error_message=str(exc)
        )
