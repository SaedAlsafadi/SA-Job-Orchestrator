"""ATS Discovery Providers."""

from typing import Any, Dict, List
from datetime import datetime, UTC

from app.core.job_discovery.discovery_provider import DiscoveryProvider, ProviderCapabilities
from app.core.connectors.workable_source import WorkableJobSource
from app.core.connectors.greenhouse_source import GreenhouseJobSource
from app.core.connectors.lever_source import LeverJobSource

class BaseATSProvider(DiscoveryProvider):
    def __init__(self, ats_source):
        self.source = ats_source

    def name(self) -> str:
        return self.source.name()

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            global_search=False,
            company_search=True,
            direct_url=True,
            filters=False,
            pagination=False
        )

    async def search(self, query: str = "", filters: Dict[str, Any] = None, **kwargs) -> List[Dict[str, Any]]:
        # ATS providers require a direct url to the company board
        url = (filters or {}).get("company_url")
        if not url:
            return []
        
        try:
            return await self.source.discover_jobs(url)
        except Exception:
            return []

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        norm = self.source.normalize_job(raw_data)
        # Ensure new expected fields exist
        norm.setdefault("raw_text", "")
        norm.setdefault("received_at", datetime.now(UTC))
        return norm

    async def health_check(self) -> bool:
        return await self.source.health_check()

class WorkableProvider(BaseATSProvider):
    def __init__(self):
        super().__init__(WorkableJobSource())

class GreenhouseProvider(BaseATSProvider):
    def __init__(self):
        super().__init__(GreenhouseJobSource())

class LeverProvider(BaseATSProvider):
    def __init__(self):
        super().__init__(LeverJobSource())
