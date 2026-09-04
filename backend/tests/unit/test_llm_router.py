import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.llm.router import LLMTaskRouter, LLMTask
from app.core.llm.client import LLMClient
from pydantic import BaseModel

class DummyResponse(BaseModel):
    answer: str

@pytest.fixture
def mock_client():
    client = MagicMock(spec=LLMClient)
    client.complete = AsyncMock()
    client.complete_with_structured_output = AsyncMock()
    return client

@pytest.fixture
def router(mock_client):
    return LLMTaskRouter(client=mock_client)

@pytest.mark.asyncio
async def test_task_routing_models(router, mock_client):
    # Test Light Task
    await router.complete(task=LLMTask.CLASSIFICATION, prompt="test")
    mock_client.complete.assert_called_with(
        prompt="test", system_prompt="", model=router.settings.light_model,
        temperature=None, max_tokens=None, response_format=None, purpose="classification"
    )
    
    # Test Heavy Task
    await router.complete(task=LLMTask.MATCH_DEEP, prompt="test2")
    mock_client.complete.assert_called_with(
        prompt="test2", system_prompt="", model=router.settings.heavy_model,
        temperature=None, max_tokens=None, response_format=None, purpose="match_deep"
    )

@pytest.mark.asyncio
async def test_legacy_configuration_avoidance():
    from app.config.settings import get_settings
    settings = get_settings()
    # Ensure preferred provider isn't implicitly breaking task routing models
    # The default_model is mapped to the light model to prevent heavy billing.
    assert settings.llm.default_model == settings.llm.light_model
    assert settings.llm.preferred_provider != "gemini"

@pytest.mark.asyncio
async def test_structured_output_routing(router, mock_client):
    await router.complete_with_structured_output(
        task=LLMTask.CV_TAILOR, prompt="test", output_schema=DummyResponse
    )
    mock_client.complete_with_structured_output.assert_called_with(
        prompt="test", output_schema=DummyResponse, system_prompt="",
        model=router.settings.heavy_model, purpose="cv_tailor"
    )

@pytest.mark.asyncio
async def test_explicit_model_bypasses_fallback_chain():
    # We verify the client logic
    client = LLMClient()
    chain = client._get_model_chain("openrouter/deepseek/deepseek-v4-flash-0731")
    assert chain == ["openrouter/deepseek/deepseek-v4-flash-0731"]
    assert len(chain) == 1 # NO Fallbacks!

