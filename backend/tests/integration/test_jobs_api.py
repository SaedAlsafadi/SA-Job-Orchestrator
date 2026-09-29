"""Integration tests for the Jobs API routes."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.job import Job
from app.schemas.job import JobListResponse
from app.schemas.matching import (
    CandidateMatchResult,
    DimensionScore,
    DimensionStatus,
    MatchDimensions,
    MatchProvenance,
    MatchVerdict,
)
from app.services import job_search as job_service
from app.services.eligibility import EligibilityResult

API_PREFIX = "/api/v1/jobs"


@pytest.fixture
def job_data(sample_job_data):
    """Provide sample_job_data with skills_required as a dict (matching schema)."""
    data = dict(sample_job_data)
    data["skills_required"] = {"python": True, "fastapi": True, "postgresql": True}
    return data


class TestSearchJobs:
    """Tests for POST /api/v1/jobs/search."""

    async def test_search_returns_empty_results(self, client, monkeypatch):
        # Job discovery has optional live providers. Keep the route test
        # deterministic and verify the current service response contract.
        monkeypatch.setattr(
            job_service,
            "search_jobs",
            AsyncMock(
                return_value=JobListResponse(
                    items=[], total=0, page=1, page_size=20, has_next=False
                )
            ),
        )
        response = await client.post(
            f"{API_PREFIX}/search",
            json={"query": "python developer", "location": "Remote"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1
        assert body["has_next"] is False

    async def test_search_requires_query(self, client):
        response = await client.post(f"{API_PREFIX}/search", json={})

        assert response.status_code == 422

    async def test_search_rejects_empty_query(self, client):
        response = await client.post(f"{API_PREFIX}/search", json={"query": ""})

        assert response.status_code == 422


class TestListJobs:
    """Tests for GET /api/v1/jobs/."""

    async def test_list_empty(self, client):
        response = await client.get(f"{API_PREFIX}/")

        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1
        assert body["has_next"] is False

    async def test_list_with_pagination_params(self, client):
        response = await client.get(
            f"{API_PREFIX}/", params={"page": 2, "page_size": 5}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["page"] == 2
        assert body["page_size"] == 5

    async def test_list_returns_created_job(self, client, db_session, job_data):
        job = Job(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        response = await client.get(f"{API_PREFIX}/")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["title"] == "Senior Python Developer"
        assert body["items"][0]["company"] == "TechCorp Inc."

    async def test_list_filter_by_status(self, client, db_session, job_data):
        job = Job(**job_data)
        db_session.add(job)
        await db_session.commit()

        response = await client.get(f"{API_PREFIX}/", params={"status": "new"})
        assert response.status_code == 200
        assert response.json()["total"] == 1

        response = await client.get(f"{API_PREFIX}/", params={"status": "applied"})
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestGetJob:
    """Tests for GET /api/v1/jobs/{job_id}."""

    async def test_get_nonexistent_returns_404(self, client):
        response = await client.get(f"{API_PREFIX}/nonexistent-id")

        assert response.status_code == 404

    async def test_get_existing_job(self, client, db_session, job_data):
        job = Job(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        response = await client.get(f"{API_PREFIX}/{job.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == job.id
        assert body["title"] == "Senior Python Developer"
        assert body["platform"] == "linkedin"
        assert body["remote"] is True


class TestAnalyzeJob:
    """Tests for POST /api/v1/jobs/{job_id}/analyze."""

    async def test_analyze_nonexistent_returns_404(self, client):
        response = await client.post(f"{API_PREFIX}/nonexistent-id/analyze")

        assert response.status_code == 404

    async def test_analyze_existing_job(
        self, client, db_session, job_data, monkeypatch
    ):
        job = Job(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        valid_dimension = DimensionScore(
            status=DimensionStatus.VALID_SCORE,
            score=82,
            explanation="Deterministic API fixture",
        )
        result = CandidateMatchResult(
            eligibility=EligibilityResult(is_eligible=True, status="PASS"),
            total_score=82,
            verdict=MatchVerdict.GOOD_MATCH,
            confidence=0.9,
            data_quality="HIGH",
            explanation="Strong overlap with the role requirements.",
            recommendation="apply",
            dimensions=MatchDimensions(
                skills=valid_dimension,
                experience=valid_dimension,
                role_alignment=valid_dimension,
            ),
            strong_matches=["Python"],
            provenance=MatchProvenance(
                candidate_profile_version=1,
                matching_algorithm_version="test",
                model_provider="test",
                model_name="test",
                generated_at=datetime.now(UTC),
            ),
        )
        monkeypatch.setattr(job_service, "analyze_job", AsyncMock(return_value=result))

        response = await client.post(f"{API_PREFIX}/{job.id}/analyze")

        assert response.status_code == 200
        body = response.json()
        assert body["total_score"] == 82
        assert body["verdict"] == "GOOD_MATCH"
        assert body["dimensions"]["skills"]["score"] == 82
        assert body["strong_matches"] == ["Python"]


class TestDeleteJob:
    """Tests for DELETE /api/v1/jobs/{job_id}."""

    async def test_delete_nonexistent_returns_404(self, client):
        response = await client.delete(f"{API_PREFIX}/nonexistent-id")

        assert response.status_code == 404

    async def test_delete_existing_job(self, client, db_session, job_data):
        job = Job(**job_data)
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        response = await client.delete(f"{API_PREFIX}/{job.id}")
        assert response.status_code == 204

        # Verify job is gone
        response = await client.get(f"{API_PREFIX}/{job.id}")
        assert response.status_code == 404
