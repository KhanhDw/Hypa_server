import logging
from abc import ABC, abstractmethod
from typing import Optional
from cachetools import TTLCache
from app.core.models import Metadata

# Import settings
from app.core.config import settings

logger = logging.getLogger(__name__)

class CacheInterface(ABC):
    """Interface for caching following the Dependency Inversion Principle"""

    @abstractmethod
    def get(self, key: str) -> Optional[Metadata]:
        """
        Get metadata from cache.

        Args:
            key: The cache key (typically a URL)

        Returns:
            The cached Metadata object if found, None otherwise
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Metadata) -> None:
        """
        Set metadata in cache.

        Args:
            key: The cache key (typically a URL)
            value: The Metadata object to cache
        """
        pass

class MetadataCache(CacheInterface):
    """
    TTL Cache for metadata with configurable size and TTL.
    This class provides thread-safe caching with automatic expiration.
    """

    def __init__(self, maxsize: int = None, ttl: int = None):
        """
        Initialize the cache.

        Args:
            maxsize: Maximum number of items to cache (uses config default if None)
            ttl: Time to live in seconds (uses config default if None)
        """
        if maxsize is None:
            maxsize = settings.cache_maxsize
        if ttl is None:
            ttl = settings.cache_ttl_seconds
            
        self.cache: TTLCache[str, Metadata] = TTLCache(maxsize=maxsize, ttl=ttl)

    def get(self, key: str) -> Optional[Metadata]:
        """
        Get metadata from cache.

        Args:
            key: The cache key (typically a URL)

        Returns:
            The cached Metadata object if found, None otherwise
        """
        logger.debug(f"Checking cache for key: {key}")
        cached_item = self.cache.get(key)
        if cached_item:
            logger.debug(f"Cache hit for key: {key}")
        else:
            logger.debug(f"Cache miss for key: {key}")
        return cached_item

    def set(self, key: str, value: Metadata) -> None:
        """
        Set metadata in cache.

        Args:
            key: The cache key (typically a URL)
            value: The Metadata object to cache
        """
        logger.debug(f"Storing metadata in cache for key: {key}")
        self.cache[key] = value