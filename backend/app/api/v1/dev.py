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
    # Check if Gemini key exists
    if not settings.llm.gemini_api_key.get_secret_value():
        return LLMHealthResponse(
            provider="gemini",
            model=settings.llm.default_model,
            success=False,
            latency_ms=0.0,
            error_message="GEMINI_API_KEY is not configured in .env"
        )
    
    client = LLMClient()
    
    try:
        start_time = time.perf_counter()
        # Minimal request to Gemini
        response = await client.complete(
            prompt="Reply with the exact word 'OK'",
            model=settings.llm.default_model,
            temperature=0.0,
            max_tokens=10
        )
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        success = response.content.strip() == "OK"
        
        return LLMHealthResponse(
            provider=response.provider,
            model=response.model,
            success=success,
            latency_ms=latency_ms,
            error_message=None if success else f"Unexpected response: {response.content}"
        )
    except Exception as exc:
        return LLMHealthResponse(
            provider="gemini",
            model=settings.llm.default_model,
            success=False,
            latency_ms=0.0,
            error_message=str(exc)
        )
