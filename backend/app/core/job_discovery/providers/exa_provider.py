"""Exa Discovery Provider."""

from datetime import UTC, datetime
from typing import Any

from app.config.settings import get_settings
from app.core.job_discovery.discovery_provider import (
    DiscoveryProvider,
    ProviderCapabilities,
)
from app.core.job_discovery.exa_search import ExaJobSearch


class ExaDiscoveryProvider(DiscoveryProvider):
    def __init__(self) -> None:
        self.api_key = get_settings().exa_api_key.get_secret_value()
        self.client = ExaJobSearch(api_key=self.api_key)

    def name(self) -> str:
        return "exa"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            global_search=True,
            company_search=False,
            direct_url=False,
            filters=True,
            pagination=False,
        )

    async def search(
        self, query: str = "", filters: dict[str, Any] | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        if not self.client.available:
            return []

        location = filters.get("location") if filters else None

        # We reuse the existing exa_search logic, but we need the raw dicts, not the JobListing objects.
        # Actually ExaJobSearch.search_jobs returns JobListing objects. Let's just dump them to dicts.
        listings = await self.client.search_jobs(query=query, location=location)

        raw_results = []
        for l in listings:
            d = l.model_dump()
            # ExaJobSearch puts some fields differently, let's map them to be ready for normalize()
            raw_results.append(
                {
                    "title": d.get("title"),
                    "company": d.get("company"),
                    "location": d.get("location"),
                    "url": d.get("url"),
                    "description": d.get("description"),
                    "platform_job_id": d.get("platform_job_id"),
                    "remote": d.get("remote"),
                    "employment_type": d.get("employment_type"),
                }
            )

        return raw_results

    def normalize(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": raw_data.get("title") or "Unknown Position",
            "company": raw_data.get("company") or "Unknown",
            "description": raw_data.get("description") or "",
            "location": raw_data.get("location") or "",
            "url": raw_data.get("url") or "",
            "platform_job_id": raw_data.get("platform_job_id") or "",
            "remote": raw_data.get("remote", False),
            "employment_type": raw_data.get("employment_type", ""),
            "raw_data": raw_data,
            "raw_text": "",
            "received_at": datetime.now(UTC),
        }

    async def health_check(self) -> bool:
        return self.client.available
