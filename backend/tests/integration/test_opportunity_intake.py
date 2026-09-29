from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import Request, Response

from app.core.job_discovery.manual_provider import ManualProvider
from app.core.job_discovery.url_provider import SSRFSecurityError, UrlProvider
from app.models.enums import JobStatus


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
async def test_invalid_url_is_rejected_before_persistence(client):
    response = await client.post(
        "/api/v1/opportunities/ingest",
        json={"text": "not a job URL", "source_type": "url"},
    )
    assert response.status_code == 422
    assert "valid public HTTP(S) job URL" in response.text


@pytest.mark.asyncio
async def test_url_extraction(monkeypatch):
    provider = UrlProvider()

    # Mock httpx
    async def mock_get(url, *args, **kwargs):
        class MockClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                pass

            async def get(self, url, *args, **kwargs):
                return Response(
                    200,
                    request=Request("GET", url),
                    text="<html><body><script>ignore me</script>We are hiring a Senior Engineer at Acme Corp!</body></html>",
                    headers={"content-type": "text/html"},
                )

        return MockClient()

    monkeypatch.setattr("httpx.AsyncClient", mock_get)

    # Note: LLM call in ingest() would normally require mocking the LLMClient.
    # For this unit test, we just test the internal text extraction method.
    html = "<html><body><script>ignore me</script>We are hiring a Senior Engineer at Acme Corp!</body></html>"
    text = provider._extract_text(html)
    assert "ignore me" not in text
    assert "We are hiring" in text


def test_url_extraction_preserves_jobposting_json_ld():
    provider = UrlProvider()
    html = """
    <html><body>
      <script type="application/ld+json">
        {"@type":"JobPosting","title":"Network Engineer",
         "description":"Maintain the radio access network.",
         "hiringOrganization":{"name":"Ericsson"}}
      </script>
      <script>window.noise = "ignore me"</script>
      <main>Careers</main>
    </body></html>
    """

    text = provider._extract_text(html)

    assert "title: Network Engineer" in text
    assert "Maintain the radio access network" in text
    assert 'hiringOrganization: {"name": "Ericsson"}' in text
    assert "ignore me" not in text


@pytest.mark.asyncio
async def test_url_fetch_retries_transient_transport_errors(monkeypatch):
    provider = UrlProvider()
    attempts = 0
    real_async_client = httpx.AsyncClient

    async def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("temporary TLS reset", request=request)
        return httpx.Response(
            200,
            request=request,
            text="<html><body>complete posting</body></html>",
            headers={"content-type": "text/html"},
        )

    def client_factory(**kwargs):
        return real_async_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(
        "app.core.job_discovery.url_provider.httpx.AsyncClient", client_factory
    )
    sleep = AsyncMock()
    monkeypatch.setattr("app.core.job_discovery.url_provider.asyncio.sleep", sleep)

    result = await provider._fetch_url("https://jobs.example.com/42")

    assert "complete posting" in result
    assert attempts == 3
    assert sleep.await_count == 2


@pytest.mark.asyncio
async def test_manual_provider_normalization():
    provider = ManualProvider()

    raw_data = {
        "title": "Software Engineer",
        "company": "TechInc",
        "detected_language": "ENGLISH",
    }

    normalized = provider.normalize(raw_data)
    assert normalized["title"] == "Software Engineer"
    assert normalized["company"] == "TechInc"
    assert normalized["detected_language"] == "ENGLISH"
    assert normalized["url"] == ""


@pytest.mark.asyncio
async def test_ingest_fails_loudly_without_queue(client, db_session):
    """No Redis/arq pool behind the app: the job must be marked FAILED with a
    clear error instead of being left in PROCESSING with the UI polling forever."""
    from app.models.job import Job

    resp = await client.post(
        "/api/v1/opportunities/ingest",
        json={"text": "https://example.com/jobs/42", "source_type": "url"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"

    job = await db_session.get(Job, body["job_id"])
    assert job.status == JobStatus.FAILED
    assert "Redis" in job.raw_data["error"]


@pytest.mark.asyncio
async def test_ingest_retries_failed_job(client, db_session):
    """Re-ingesting a FAILED job resets it for re-processing (retry semantics),
    so a transient infrastructure failure never permanently blocks a URL."""
    from app.models.job import Job

    resp = await client.post(
        "/api/v1/opportunities/ingest",
        json={"text": "https://example.com/jobs/43", "source_type": "url"},
    )
    job_id = resp.json()["job_id"]

    # Simulate an earlier, different failure on the row.
    job = await db_session.get(Job, job_id)
    job.raw_data = {"error": "old scrape failure"}
    await db_session.commit()

    resp2 = await client.post(
        "/api/v1/opportunities/ingest",
        json={"text": "https://example.com/jobs/43", "source_type": "url"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["job_id"] == job_id

    # The retry path ran: the old error was cleared and replaced by the current
    # queue-unavailable error (return-as-is would have kept the old message).
    await db_session.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.raw_data["error"] != "old scrape failure"
    assert "Redis" in job.raw_data["error"]


@pytest.mark.asyncio
async def test_ingest_retry_uses_stable_source_after_normalization(client, db_session):
    """Worker normalization changes platform_job_id, but the same source URL
    must still retry the original tenant-owned job instead of creating a duplicate."""
    from app.models.job import Job

    source_url = "https://example.com/jobs/normalized-44"
    first = await client.post(
        "/api/v1/opportunities/ingest",
        json={"text": source_url, "source_type": "url"},
    )
    job_id = first.json()["job_id"]

    job = await db_session.get(Job, job_id)
    job.platform_job_id = "normalized-content-hash"
    job.status = JobStatus.FAILED
    await db_session.commit()

    retry = await client.post(
        "/api/v1/opportunities/ingest",
        json={"text": source_url, "source_type": "url"},
    )

    assert retry.status_code == 200
    assert retry.json()["job_id"] == job_id
