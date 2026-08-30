"""Tests for Opportunity Ingestion and Route Resolution."""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, patch

from app.models.job import Job
from app.services.application_route_resolver import ApplicationRouteResolver
from app.api.v1.opportunities import IngestOpportunityRequest, ingest_opportunity

@pytest.fixture
def mock_job():
    return Job(
        id="test-job-id",
        title="Software Engineer",
        company="Acme Corp",
        description="Great job.",
        url="",
    )

@pytest.mark.asyncio
async def test_explicit_workable_url(mock_job):
    resolver = ApplicationRouteResolver()
    mock_job.application_url = "https://apply.workable.com/acme"
    routes = await resolver.resolve(mock_job)
    
    assert len(routes) == 1
    assert routes[0].route_type == "WORKABLE"
    assert routes[0].confidence == 1.0
    assert routes[0].is_preferred is True
    assert routes[0].requires_human is False

@pytest.mark.asyncio
async def test_explicit_greenhouse_url(mock_job):
    resolver = ApplicationRouteResolver()
    mock_job.application_url = "https://boards.greenhouse.io/acme/jobs/123"
    routes = await resolver.resolve(mock_job)
    
    assert len(routes) == 1
    assert routes[0].route_type == "GREENHOUSE"

@pytest.mark.asyncio
async def test_explicit_lever_url(mock_job):
    resolver = ApplicationRouteResolver()
    mock_job.application_url = "https://jobs.lever.co/acme/123"
    routes = await resolver.resolve(mock_job)
    
    assert len(routes) == 1
    assert routes[0].route_type == "LEVER"

@pytest.mark.asyncio
async def test_company_website_url(mock_job):
    resolver = ApplicationRouteResolver()
    mock_job.application_url = "https://careers.acme.com/apply"
    routes = await resolver.resolve(mock_job)
    
    assert len(routes) == 1
    assert routes[0].route_type == "COMPANY_WEBSITE"
    assert routes[0].confidence == 0.9

@pytest.mark.asyncio
async def test_deterministic_email_regex(mock_job):
    resolver = ApplicationRouteResolver()
    mock_job.raw_text = "Looking for a python dev. Send CV to jobs@acme.com and wait."
    routes = await resolver.resolve(mock_job)
    
    assert len(routes) == 1
    assert routes[0].route_type == "EMAIL"
    assert routes[0].email == "jobs@acme.com"
    assert routes[0].confidence == 0.9
    assert routes[0].requires_human is False

@pytest.mark.asyncio
async def test_multiple_competing_routes(mock_job):
    resolver = ApplicationRouteResolver()
    # Has both ATS URL and an email
    mock_job.application_url = "https://apply.workable.com/acme"
    mock_job.raw_text = "Or you can send cv to careers@acme.com"
    
    routes = await resolver.resolve(mock_job)
    
    assert len(routes) == 2
    # Ensure ranked correctly (Workable > Email)
    assert routes[0].route_type == "WORKABLE"
    assert routes[0].is_preferred is True
    assert routes[1].route_type == "EMAIL"
    assert routes[1].is_preferred is False

@pytest.mark.asyncio
@patch("app.core.llm.client.LLMClient.complete")
async def test_llm_fallback_route(mock_complete, mock_job):
    class MockResp: content = '{"route_type": "COMPANY_WEBSITE", "url": "https://unknown.com", "confidence": 0.5}'
    mock_complete.return_value = MockResp()
    resolver = ApplicationRouteResolver()
    mock_job.raw_text = "Apply on our weird portal at unknown.com"
    
    routes = await resolver.resolve(mock_job)
    assert len(routes) == 1
    assert routes[0].route_type == "COMPANY_WEBSITE"
    assert routes[0].confidence == 0.5
    assert routes[0].requires_human is True  # Because < 0.6 confidence

@pytest.mark.asyncio
@patch("app.core.llm.client.LLMClient.complete")
async def test_no_route(mock_complete, mock_job):
    class MockResp: content = '{"route_type": "MANUAL", "confidence": 0.1}'
    mock_complete.return_value = MockResp()
    resolver = ApplicationRouteResolver()
    mock_job.raw_text = "We are hiring. That's all."
    
    routes = await resolver.resolve(mock_job)
    assert len(routes) == 1
    assert routes[0].route_type == "MANUAL"
    assert routes[0].requires_human is True

@pytest.mark.asyncio
@patch("app.core.job_discovery.manual_provider.LLMClient.complete")
async def test_ingest_whatsapp_style(mock_complete):
    class MockResp: content = '{"title": "Dev", "company": "Acme", "location": "Riyadh", "application_email": "hr@acme.com"}'
    mock_complete.return_value = MockResp()
    
    from app.core.job_discovery.manual_provider import ManualProvider
    provider = ManualProvider()
    raw = await provider.ingest("Hiring Dev at Acme Riyadh! hr@acme.com", title_override="Senior Dev")
    norm = provider.normalize(raw)
    
    assert raw["title"] == "Senior Dev"  # override worked
    assert norm["title"] == "Senior Dev"
    assert norm["company"] == "Acme"
    assert norm["raw_text"] == "Hiring Dev at Acme Riyadh! hr@acme.com"
    assert "received_at" in norm
