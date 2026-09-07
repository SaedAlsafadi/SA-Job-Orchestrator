"""URL Opportunity Provider for web ingestion."""

import json
import re
import socket
import urllib.parse
from typing import Any, Dict
from datetime import datetime, UTC
import httpx
import structlog
from bs4 import BeautifulSoup

from app.core.job_discovery.opportunity_source import UserFedOpportunitySource
from app.core.llm.client import LLMClient
from app.core.llm.router import LLMTaskRouter, LLMTask
from app.core.llm.prompts.opportunity_extraction import OPPORTUNITY_EXTRACTION_PROMPT

logger = structlog.get_logger(__name__)

class SSRFSecurityError(Exception):
    """Raised when a URL violates SSRF protections."""
    pass

class UrlProvider(UserFedOpportunitySource):
    """Fetches job opportunities from generic URLs with SSRF protection."""
    
    def name(self) -> str:
        return "url"
        
    async def health_check(self) -> bool:
        return True
        
    def _validate_url(self, url: str) -> None:
        """Validate URL against SSRF and basic security constraints."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise SSRFSecurityError("Only HTTP and HTTPS schemes are allowed.")
            
        hostname = parsed.hostname
        if not hostname:
            raise SSRFSecurityError("Invalid URL hostname.")
            
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            raise SSRFSecurityError("Localhost is not allowed.")
            
        # Block private IP ranges
        if re.match(r"^(10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.|127\.|169\.254\.)", hostname):
            raise SSRFSecurityError("Private IP addresses are not allowed.")

    async def _fetch_url(self, url: str) -> str:
        """Fetch URL content."""
        self._validate_url(url)
        
        async with httpx.AsyncClient(
            follow_redirects=True, 
            max_redirects=5, 
            timeout=10.0,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64 AppleWebKit/537.36)"}
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                raise ValueError(f"Unsupported content type: {content_type}")
                
            return resp.text

    def _extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()
        
        text = soup.get_text(separator="\n", strip=True)
        return text

    async def ingest(self, input_text: str, **kwargs) -> Dict[str, Any]:
        """Ingest URL and use LLM to extract JSON from unstructured text.
        Here, `input_text` is the URL.
        """
        url = input_text.strip()
        logger.info("url_provider.fetching", url=url)
        html = await self._fetch_url(url)
        
        text_content = self._extract_text(html)
        if len(text_content) < 50:
            raise ValueError("Extracted text is too short, page might be client-side rendered or blocked.")
            
        # Limit text size for LLM
        text_content = text_content[:20000]

        client = LLMTaskRouter(LLMClient())
        response = await client.complete(
            task=LLMTask.JOB_NORMALIZATION,
            system_prompt=OPPORTUNITY_EXTRACTION_PROMPT,
            prompt=f"Extract job opportunity from the following text parsed from {url}:\n\n{text_content}",
            temperature=0.0
        )
        try:
            cleaned = response.content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
                
            extracted = json.loads(cleaned.strip())
        except Exception:
            extracted = {
                "title": "Unknown Job Opportunity",
                "company": "Unknown",
                "description": text_content[:500] + "...",
            }
            
        extracted["_raw_text"] = text_content
        extracted["_received_at"] = datetime.now(UTC).isoformat()
        extracted["_original_url"] = url
        
        if kwargs.get("title_override"):
            extracted["title"] = kwargs["title_override"]
        if kwargs.get("company_override"):
            extracted["company"] = kwargs["company_override"]
            
        return extracted

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize the extracted dictionary into canonical schema fields."""
        return {
            "title": raw_data.get("title") or "Unknown Position",
            "company": raw_data.get("company") or "Confidential",
            "description": raw_data.get("description") or "",
            "location": raw_data.get("location") or "",
            "requirements": raw_data.get("requirements") or "",
            "salary_range": raw_data.get("salary_range"),
            "remote": raw_data.get("remote") or False,
            "employment_type": raw_data.get("employment_type"),
            "detected_language": raw_data.get("detected_language") or "UNKNOWN",
            "url": raw_data.get("_original_url") or raw_data.get("application_url") or "",
            "application_url": raw_data.get("application_url"),
            "raw_data": raw_data,
            "raw_text": raw_data.get("_raw_text", ""),
            "received_at": datetime.fromisoformat(raw_data.get("_received_at")) if raw_data.get("_received_at") else datetime.now(UTC)
        }
