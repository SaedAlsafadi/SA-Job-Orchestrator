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
            submission=True,
            status_monitoring=False
        )

    def _extract_account(self, url: str) -> str:
        # e.g. https://apply.workable.com/company-name/
        # or https://apply.workable.com/company-name/j/12345
        match = re.search(r"apply\.workable\.com/([a-zA-Z0-9-]+)", url)
        if match:
            return match.group(1)
            
        # e.g. https://jobs.workable.com/en/view/ww7scbfrJsQ5jU9qjNLada/document-controller-in-riyadh-at-hanmiglobal-saudi
        match_jobs = re.search(r"jobs\.workable\.com/.+?-at-([a-zA-Z0-9-]+)", url)
        if match_jobs:
            return match_jobs.group(1)
            
        raise ValueError(f"Could not extract workable account from URL: {url}")

    async def _fetch_jobs_for_account(self, client: httpx.AsyncClient, account: str) -> List[Dict[str, Any]]:
        api_url = f"https://apply.workable.com/api/v3/accounts/{account}/jobs"
        payload = {"query":"","location":[],"department":[],"worktype":[],"remote":[]}
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
        res = await client.post(api_url, json=payload, headers=headers)
        res.raise_for_status()
        data = res.json()
        results = data.get("results", [])
        for r in results:
            if "url" not in r and "shortcode" in r:
                r["url"] = f"https://apply.workable.com/{account}/j/{r['shortcode']}/"
        return results

    async def discover_jobs(self, url: str) -> List[Dict[str, Any]]:
        from fastapi import HTTPException
        account = self._extract_account(url)
        
        async with httpx.AsyncClient() as client:
            try:
                return await self._fetch_jobs_for_account(client, account)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    if "jobs.workable.com" in url:
                        # The URL slug account name was incorrect. Fetch HTML and extract real subdomain.
                        page_res = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                        subdomain_match = re.search(r'"subdomain":"([^"]+)"', page_res.text)
                        if subdomain_match:
                            real_account = subdomain_match.group(1)
                            try:
                                return await self._fetch_jobs_for_account(client, real_account)
                            except httpx.HTTPStatusError:
                                pass # Fall through to the generic 400 error below
                    raise HTTPException(status_code=400, detail="Job board not found. The Workable URL may be invalid, expired, or private.")
                raise HTTPException(status_code=400, detail=f"Failed to fetch Workable jobs: {e.response.status_code}")

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
            "application_url": raw_job.get("url").rstrip("/") + "/apply" if raw_job.get("url") else None,
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
