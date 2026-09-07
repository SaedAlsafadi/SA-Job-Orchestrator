import pytest
import urllib.parse
from app.core.job_discovery.url_provider import UrlProvider, SSRFSecurityError
from app.core.job_discovery.manual_provider import ManualProvider
from app.models.enums import JobStatus
from app.schemas.matching import CandidateMatchResult
from httpx import Response, Request

@pytest.mark.asyncio
async def test_ssrf_protections():
    provider = UrlProvider()
    
    with pytest.raises(SSRFSecurityError):
        provider._validate_url("file:///etc/passwd")
        
    with pytest.raises(SSRFSecurityError):
        provider._validate_url("http://localhost:8080/admin")
        
    with pytest.raises(SSRFSecurityError):
        provider._validate_url("http://127.0.0.1/status")
        
    with pytest.raises(SSRFSecurityError):
        provider._validate_url("http://169.254.169.254/latest/meta-data")
        
    with pytest.raises(SSRFSecurityError):
        provider._validate_url("http://10.0.0.1/internal")
        
    # Should not raise
    provider._validate_url("https://boards.greenhouse.io/openai/jobs/12345")

@pytest.mark.asyncio
async def test_url_extraction(monkeypatch):
    provider = UrlProvider()
    
    # Mock httpx
    async def mock_get(url, *args, **kwargs):
        class MockClient:
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc, tb): pass
            async def get(self, url, *args, **kwargs):
                return Response(200, request=Request("GET", url), text="<html><body><script>ignore me</script>We are hiring a Senior Engineer at Acme Corp!</body></html>", headers={"content-type": "text/html"})
        return MockClient()
        
    monkeypatch.setattr("httpx.AsyncClient", mock_get)
    
    # Note: LLM call in ingest() would normally require mocking the LLMClient. 
    # For this unit test, we just test the internal text extraction method.
    html = "<html><body><script>ignore me</script>We are hiring a Senior Engineer at Acme Corp!</body></html>"
    text = provider._extract_text(html)
    assert "ignore me" not in text
    assert "We are hiring" in text

@pytest.mark.asyncio
async def test_manual_provider_normalization():
    provider = ManualProvider()
    
    raw_data = {
        "title": "Software Engineer",
        "company": "TechInc",
        "detected_language": "ENGLISH"
    }
    
    normalized = provider.normalize(raw_data)
    assert normalized["title"] == "Software Engineer"
    assert normalized["company"] == "TechInc"
    assert normalized["detected_language"] == "ENGLISH"
    assert normalized["url"] == ""

