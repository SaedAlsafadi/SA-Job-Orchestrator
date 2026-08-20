import httpx
import re
from datetime import datetime
from typing import Any, Dict, List
import structlog
from app.core.connectors.base import JobSource

logger = structlog.get_logger(__name__)

class GreenhouseJobSource(JobSource):
    def name(self) -> str:
        return "greenhouse"

    def _extract_board_token(self, url: str) -> str:
        # e.g., https://boards.greenhouse.io/companyname or https://boards.eu.greenhouse.io/companyname
        match = re.search(r"boards\.(?:eu\.)?greenhouse\.io/([^/]+)", url)
        if match:
            return match.group(1)
        raise ValueError(f"Could not extract Greenhouse board token from URL: {url}")

    async def discover_jobs(self, url: str) -> List[Dict[str, Any]]:
        board_token = self._extract_board_token(url)
        # Try US first, then EU if 404
        api_urls = [
            f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true",
            f"https://boards-api.eu.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        ]
        
        async with httpx.AsyncClient() as client:
            headers = {"User-Agent": "Mozilla/5.0 SA-Job-Orchestrator"}
            for api_url in api_urls:
                res = await client.get(api_url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("jobs", [])
                elif res.status_code != 404:
                    res.raise_for_status()
            return []

    async def fetch_job(self, external_job_id: str) -> Dict[str, Any]:
        raise NotImplementedError("fetch_job not implemented for Greenhouse")

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        location_str = raw_job.get("location", {}).get("name", "")
        
        # Greenhouse often returns a lot of HTML in the "content" field
        content_html = raw_job.get("content", "")
        # We naively map content to description. In a real system, we'd clean HTML.
        
        return {
            "platform": self.name(),
            "platform_job_id": str(raw_job.get("id")),
            "title": raw_job.get("title", ""),
            "company": "Greenhouse Employer", # Greenhouse API v1 usually requires a separate boards call for company name
            "location": location_str,
            "country": None,
            "city": location_str,
            "url": raw_job.get("absolute_url", ""),
            "application_url": raw_job.get("absolute_url", ""),
            "description": content_html,
            "requirements": "",
            "employment_type": "",
            "remote": "remote" in location_str.lower(),
            "work_model": "remote" if "remote" in location_str.lower() else "onsite",
            "posted_date": datetime.strptime(raw_job["updated_at"][:19], "%Y-%m-%dT%H:%M:%S") if raw_job.get("updated_at") else None,
            "raw_data": raw_job
        }

    async def health_check(self) -> bool:
        return True
