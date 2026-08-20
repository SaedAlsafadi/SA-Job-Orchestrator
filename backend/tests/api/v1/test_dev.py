import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_llm_health_endpoint_no_key(anon_client, monkeypatch: pytest.MonkeyPatch):
    # Ensure no API key is set for this test
    monkeypatch.setenv("LLM__GEMINI_API_KEY", "")
    
    response = await anon_client.get("/api/v1/dev/llm-health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["provider"] == "gemini"
    assert data["success"] is False
    assert "not configured" in data["error_message"]
