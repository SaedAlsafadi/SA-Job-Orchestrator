"""Application Route Resolver."""

import re
from typing import List
from datetime import datetime, UTC

from app.models.job import Job
from app.models.application_route import ApplicationRoute

import json
from app.core.llm.prompts.route_extraction import ROUTE_EXTRACTION_PROMPT

class ApplicationRouteResolver:
    """Resolves the appropriate application routes for a given Job opportunity."""
    
    async def resolve(self, job: Job) -> List[ApplicationRoute]:
        """Determine application routes deterministically first, falling back to LLM if needed."""
        routes = []
        raw_payload = job.raw_source_payload or {}
        text_to_search = job.raw_text or job.description or ""
        
        # 1. Explicit Application URL
        explicit_url = job.application_url or raw_payload.get("application_url")
        if explicit_url:
            ats_route = self._detect_ats(explicit_url, job)
            if ats_route:
                routes.append(ats_route)
            else:
                # Company Website or other external link
                routes.append(ApplicationRoute(
                    job_id=job.id,
                    route_type="COMPANY_WEBSITE",
                    url=explicit_url,
                    confidence=0.9,
                    resolution_reason="Explicit application URL provided",
                    requires_human=False,
                    is_preferred=True,
                    resolved_at=datetime.now(UTC)
                ))
                
        # 2. Deterministic Email Extraction
        email_route = self._extract_email_route(text_to_search, raw_payload, job)
        if email_route:
            routes.append(email_route)
            
        # 3. Known ATS URL pattern fallback (if explicit application url wasn't an ATS, but job.url is)
        if not any(r.route_type in ["WORKABLE", "GREENHOUSE", "LEVER"] for r in routes) and job.url:
            ats_route = self._detect_ats(job.url, job)
            if ats_route:
                routes.append(ats_route)

        # 4. If nothing deterministic is found, invoke LLM semantic extraction
        if not routes and text_to_search:
            llm_route = await self._extract_route_via_llm(text_to_search, job)
            if llm_route:
                routes.append(llm_route)
                
        # Fallback if even LLM fails or no text
        if not routes:
            routes.append(ApplicationRoute(
                job_id=job.id,
                route_type="MANUAL",
                confidence=0.0,
                resolution_reason="No deterministic route found. LLM semantic extraction not invoked or failed.",
                requires_human=True,
                is_preferred=True,
                resolved_at=datetime.now(UTC)
            ))
            
        # Determine preferred route if not already set
        if len(routes) > 1:
            # Rank routes: Workable/Greenhouse/Lever > Email > Company Website
            rank = {"WORKABLE": 10, "GREENHOUSE": 10, "LEVER": 10, "EMAIL": 8, "COMPANY_WEBSITE": 5, "LINKEDIN": 5, "MANUAL": 0}
            routes.sort(key=lambda r: (rank.get(r.route_type, 0), r.confidence), reverse=True)
            for i, route in enumerate(routes):
                route.is_preferred = (i == 0)

        # If highest confidence is below threshold, require human
        if routes[0].confidence < 0.6:
            routes[0].requires_human = True

        return routes

    async def _extract_route_via_llm(self, text: str, job: Job) -> ApplicationRoute | None:
        """Use LLM to semantically infer the application route when ambiguous."""
        try:
            from app.core.llm.client import LLMClient
            client = LLMClient()
            response = await client.complete(
                system_prompt=ROUTE_EXTRACTION_PROMPT,
                prompt=f"Job Opportunity Text:\n\n{text}",
                temperature=0.0
            )
            cleaned = response.content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            data = json.loads(cleaned.strip())
            
            return ApplicationRoute(
                job_id=job.id,
                route_type=data.get("route_type", "MANUAL"),
                url=data.get("url"),
                email=data.get("email"),
                instructions=data.get("instructions"),
                confidence=float(data.get("confidence", 0.5)),
                resolution_reason="LLM semantic interpretation",
                requires_human=data.get("confidence", 0.5) < 0.8,
                is_preferred=False,
                resolved_at=datetime.now(UTC)
            )
        except Exception as e:
            return None

    def _detect_ats(self, url: str, job: Job) -> ApplicationRoute | None:
        """Deterministically detect ATS from URL without scraping."""
        url_lower = url.lower()
        if "workable.com" in url_lower:
            return ApplicationRoute(
                job_id=job.id,
                route_type="WORKABLE",
                url=url,
                confidence=1.0,
                resolution_reason="Deterministic Workable URL match",
                requires_human=False,
                is_preferred=True,
                resolved_at=datetime.now(UTC)
            )
        elif "greenhouse.io" in url_lower:
            return ApplicationRoute(
                job_id=job.id,
                route_type="GREENHOUSE",
                url=url,
                confidence=1.0,
                resolution_reason="Deterministic Greenhouse URL match",
                requires_human=False,
                is_preferred=True,
                resolved_at=datetime.now(UTC)
            )
        elif "lever.co" in url_lower:
            return ApplicationRoute(
                job_id=job.id,
                route_type="LEVER",
                url=url,
                confidence=1.0,
                resolution_reason="Deterministic Lever URL match",
                requires_human=False,
                is_preferred=True,
                resolved_at=datetime.now(UTC)
            )
        elif "bayt.com" in url_lower:
            return ApplicationRoute(
                job_id=job.id,
                route_type="BAYT",
                url=url,
                confidence=1.0,
                resolution_reason="Deterministic Bayt URL match",
                requires_human=True,  # Bayt applications require manual intervention
                is_preferred=False,
                resolved_at=datetime.now(UTC)
            )
        
        return None

    def _extract_email_route(self, text: str, raw_payload: dict, job: Job) -> ApplicationRoute | None:
        """Deterministically extract email if explicit instructions are given."""
        # 1. Check explicit fields from LLM Opportunity extraction first
        explicit_email = raw_payload.get("application_email")
        if explicit_email:
            return ApplicationRoute(
                job_id=job.id,
                route_type="EMAIL",
                email=explicit_email,
                instructions=raw_payload.get("application_instructions"),
                confidence=0.95,
                resolution_reason="Explicit application_email field found in source payload",
                requires_human=False,
                is_preferred=False, # Will be sorted later
                resolved_at=datetime.now(UTC)
            )
            
        # 2. Regex fallback for phrases like "send CV to <email>"
        email_pattern = r"(?i)(?:send|forward|email)\s+(?:your\s+)?(?:cv|resume|application)\s+to\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
        match = re.search(email_pattern, text)
        if match:
            return ApplicationRoute(
                job_id=job.id,
                route_type="EMAIL",
                email=match.group(1),
                confidence=0.9,
                resolution_reason="Regex match for 'send CV to [email]'",
                requires_human=False,
                is_preferred=False,
                resolved_at=datetime.now(UTC)
            )
            
        return None
