import httpx
import re
from datetime import datetime
from typing import Any, Dict, List
import structlog
from app.core.connectors.base import JobSource, ConnectorCapabilities

logger = structlog.get_logger(__name__)

class LeverJobSource(JobSource):
    def name(self) -> str:
        return "lever"

    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            discovery=True,
            job_details=True,
            application_preparation=True,
            prefilled_profile_detection=True,
            resume_upload=True,
            question_handling=True,
            human_review=True,
            submission=False,
            status_monitoring=False
        )

    def _extract_company(self, url: str) -> str:
        # e.g., https://jobs.lever.co/companyname or https://jobs.lever.co/companyname/job_id
        match = re.search(r"jobs\.lever\.co/([^/]+)", url)
        if match:
            return match.group(1)
        raise ValueError(f"Could not extract Lever company from URL: {url}")

    async def discover_jobs(self, url: str) -> List[Dict[str, Any]]:
        company = self._extract_company(url)
        api_url = f"https://api.lever.co/v0/postings/{company}?mode=json"
        
        async with httpx.AsyncClient() as client:
            headers = {"User-Agent": "Mozilla/5.0 SA-Job-Orchestrator"}
            res = await client.get(api_url, headers=headers)
            res.raise_for_status()
            data = res.json()
            return data if isinstance(data, list) else []

    async def fetch_job(self, external_job_id: str) -> Dict[str, Any]:
        raise NotImplementedError("fetch_job not implemented for Lever")

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        cats = raw_job.get("categories", {})
        location = cats.get("location", "")
        commitment = cats.get("commitment", "")
        team = cats.get("team", "")
        
        # Lever gives us unix timestamp
        created_at_ms = raw_job.get("createdAt")
        posted_date = datetime.fromtimestamp(created_at_ms / 1000.0) if created_at_ms else None

        return {
            "platform": self.name(),
            "platform_job_id": raw_job.get("id"),
            "title": raw_job.get("text", ""),
            "company": "Lever Employer", # Often requires separate metadata call
            "location": location,
            "country": None,
            "city": location,
            "url": raw_job.get("hostedUrl", ""),
            "application_url": raw_job.get("applyUrl", ""),
            "description": raw_job.get("descriptionPlain", ""),
            "requirements": "", # Lever usually bundles requirements inside description
            "employment_type": commitment,
            "remote": "remote" in location.lower(),
            "work_model": "remote" if "remote" in location.lower() else "onsite",
            "posted_date": posted_date,
            "raw_data": raw_job
        }

    async def health_check(self) -> bool:
        return True
