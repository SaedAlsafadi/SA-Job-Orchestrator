"""Bayt Discovery Provider."""

import re
import structlog
import httpx
from bs4 import BeautifulSoup
from typing import Any, Dict, List
from urllib.parse import urlencode, urljoin

from app.core.job_discovery.discovery_provider import DiscoveryProvider, ProviderCapabilities

logger = structlog.get_logger(__name__)


class BaytDiscoveryProvider(DiscoveryProvider):
    def name(self) -> str:
        return "bayt"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            global_search=True,
            company_search=False,
            direct_url=True,
            filters=True,
            pagination=False
        )

    async def search(self, query: str = "", filters: Dict[str, Any] = None, **kwargs) -> List[Dict[str, Any]]:
        filters = filters or {}
        location = filters.get("location", "").lower()
        country_path = "saudi-arabia" if "saudi" in location or "ksa" in location else "international"
        
        url = f"https://www.bayt.com/en/{country_path}/jobs/search/"
        params = {}
        if query:
            params["kw"] = query
            
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                
            if resp.status_code in (403, 429):
                logger.warning("bayt_provider.blocked", status_code=resp.status_code)
                # Fail gracefully if blocked by anti-bot measures, do not kill the orchestrator cycle
                return []
            
            resp.raise_for_status()
            return self._parse_search_page(resp.text, str(resp.url))
            
        except httpx.RequestError as e:
            logger.error("bayt_provider.request_failed", error=str(e))
            return []
        except Exception as e:
            logger.error("bayt_provider.unexpected_error", error=str(e))
            return []
            
    def _parse_search_page(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Bayt's list format often uses has-pointer-d or card structures.
        # This covers standard known class permutations on bayt.com
        items = soup.select("li.has-pointer-d") or soup.select(".jb-wrap") or soup.select(".job-item")
        
        for item in items:
            title_tag = item.select_one("h2.jb-title a") or item.select_one("h2 a") or item.select_one("a[data-job-id]")
            if not title_tag:
                continue
                
            title = title_tag.text.strip()
            link = title_tag.get("href")
            full_link = urljoin(base_url, link) if link else ""
            
            company_tag = item.select_one(".jb-company") or item.select_one(".company-name")
            company = company_tag.text.strip() if company_tag else ""
            
            loc_tag = item.select_one(".jb-loc") or item.select_one(".location")
            location = loc_tag.text.strip() if loc_tag else ""
            
            desc_tag = item.select_one(".jb-descr") or item.select_one(".job-desc")
            description = desc_tag.text.strip() if desc_tag else ""
            
            job_id = self._extract_job_id(full_link)
            if not job_id and item.has_attr("data-job-id"):
                job_id = item["data-job-id"]
            
            results.append({
                "title": title,
                "company": company,
                "location": location,
                "url": full_link,
                "description": description,
                "platform_job_id": job_id,
                "source_type": "bayt"
            })
            
        return results
        
    def _extract_job_id(self, url: str) -> str:
        # e.g., https://www.bayt.com/en/saudi-arabia/jobs/software-engineer-1234567/
        match = re.search(r'-(\d+)/?$', url)
        if match:
            return match.group(1)
        return ""

    def normalize(self, raw_data: Any) -> Dict[str, Any]:
        """Normalize raw data from this provider into a canonical opportunity dictionary."""
        # Include fields that existing matchers and route resolvers might use
        return {
            "title": raw_data.get("title", ""),
            "company": raw_data.get("company", ""),
            "location": raw_data.get("location", ""),
            "url": raw_data.get("url", ""),
            "description": raw_data.get("description", ""),
            "platform_job_id": raw_data.get("platform_job_id", ""),
            "platform": "bayt",
            "source_type": "bayt",
            "raw_text": f"Title: {raw_data.get('title')}\nCompany: {raw_data.get('company')}\nLocation: {raw_data.get('location')}\n\n{raw_data.get('description', '')}",
            "raw_source_payload": raw_data
        }
        
    async def health_check(self) -> bool:
        # Simple health check without hitting the search endpoint
        return True
