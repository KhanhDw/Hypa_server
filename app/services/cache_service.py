from abc import ABC, abstractmethod
from typing import Optional
from cachetools import TTLCache
from app.core.models import Metadata

class CacheInterface(ABC):
    """Interface for caching following the Dependency Inversion Principle"""

    @abstractmethod
    def get(self, key: str) -> Optional[Metadata]:
        pass

    @abstractmethod
    def set(self, key: str, value: Metadata) -> None:
        pass

class MetadataCache(CacheInterface):
    """
    TTL Cache for metadata with 100 items and 10 minute TTL
    """

    def __init__(self, maxsize: int = 100, ttl: int = 600):
        self.cache: TTLCache[str, Metadata] = TTLCache(maxsize=maxsize, ttl=ttl)

    def get(self, key: str) -> Optional[Metadata]:
        """Get metadata from cache"""
        return self.cache.get(key)

    def set(self, key: str, value: Metadata) -> None:
        """Set metadata in cache"""
        self.cache[key] = value