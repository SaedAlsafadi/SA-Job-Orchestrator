"""Base abstractions for Opportunity Discovery."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

class OpportunitySource(ABC):
    """An abstract source of job opportunities."""
    
    @abstractmethod
    def name(self) -> str:
        """Name of the source provider."""
        ...
        
    @abstractmethod
    def normalize(self, raw_data: Any) -> Dict[str, Any]:
        """Normalize raw data from this provider into a canonical opportunity dictionary."""
        ...
        
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if this source provider is available and properly configured."""
        ...


class UserFedOpportunitySource(OpportunitySource):
    """An opportunity source that processes explicitly provided single opportunities (e.g., manual paste)."""
    
    @abstractmethod
    async def ingest(self, input_text: str, **kwargs) -> Any:
        """Ingest text and return a raw structure representing the opportunity.
        This raw structure should then be pass-able to normalize().
        """
        ...


class SearchOpportunitySource(OpportunitySource):
    """An opportunity source that actively queries or scrapes a platform."""
    
    @abstractmethod
    async def discover(self, query_or_url: str, **kwargs) -> List[Any]:
        """Discover multiple opportunities based on a query or URL.
        Returns a list of raw structures.
        """
        ...
