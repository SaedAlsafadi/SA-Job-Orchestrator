"""Base abstractions for Discovery Providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pydantic import BaseModel

class ProviderCapabilities(BaseModel):
    global_search: bool = False
    company_search: bool = False
    direct_url: bool = False
    filters: bool = False
    pagination: bool = False

class DiscoveryProvider(ABC):
    """An abstract provider capable of discovering job opportunities."""
    
    @abstractmethod
    def name(self) -> str:
        """Name of the discovery provider."""
        ...
        
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Capabilities supported by this provider."""
        ...

    @abstractmethod
    async def search(self, query: str = "", filters: Dict[str, Any] = None, **kwargs) -> List[Dict[str, Any]]:
        """Discover jobs based on search criteria.
        Returns a list of raw structures suitable for normalize().
        """
        ...
        
    @abstractmethod
    def normalize(self, raw_data: Any) -> Dict[str, Any]:
        """Normalize raw data from this provider into a canonical opportunity dictionary."""
        ...
        
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if this provider is available and properly configured."""
        ...
