import httpx
import re
from datetime import datetime
from typing import Any, Dict, List
from app.core.connectors.base import JobSource, ApplicationConnector, ApplicationQuestion

class WorkableJobSource(JobSource):
    def name(self) -> str:
        return "workable"

    def capabilities(self):
        from app.core.connectors.base import ConnectorCapabilities
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

    def _extract_account(self, url: str) -> str:
        # e.g. https://apply.workable.com/company-name/
        # or https://apply.workable.com/company-name/j/12345
        match = re.search(r"apply\.workable\.com/([a-zA-Z0-9-]+)", url)
        if match:
            return match.group(1)
        raise ValueError(f"Could not extract workable account from URL: {url}")

    async def discover_jobs(self, url: str) -> List[Dict[str, Any]]:
        account = self._extract_account(url)
        api_url = f"https://apply.workable.com/api/v3/accounts/{account}/jobs"
        
        async with httpx.AsyncClient() as client:
            payload = {"query":"","location":[],"department":[],"worktype":[],"remote":[]}
            headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
            res = await client.post(api_url, json=payload, headers=headers)
            res.raise_for_status()
            data = res.json()
            return data.get("results", [])

    async def fetch_job(self, external_job_id: str) -> Dict[str, Any]:
        # Typically not needed for public workable discovery as discover_jobs returns rich data
        raise NotImplementedError("fetch_job not implemented for public workable")

    def normalize_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "platform": self.name(),
            "platform_job_id": raw_job.get("shortcode"),
            "title": raw_job.get("title"),
            "company": raw_job.get("account", {}).get("name", "Unknown Workable Company"),
            "location": raw_job.get("location", {}).get("countryName", ""),
            "country": raw_job.get("location", {}).get("countryCode", ""),
            "city": raw_job.get("location", {}).get("city", ""),
            "url": raw_job.get("url"),
            "application_url": raw_job.get("url") + "/apply" if raw_job.get("url") else None,
            "description": raw_job.get("description", ""),
            "requirements": raw_job.get("requirements", ""),
            "employment_type": raw_job.get("type", ""),
            "remote": raw_job.get("workplace", "") == "remote",
            "work_model": raw_job.get("workplace", ""),
            "posted_date": datetime.strptime(raw_job["published_on"], "%Y-%m-%d") if raw_job.get("published_on") else None,
            "raw_data": raw_job
        }

    async def health_check(self) -> bool:
        return True
