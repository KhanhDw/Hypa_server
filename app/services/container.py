from typing import Dict, Type, TypeVar
from .fetcher import URLValidator, URLValidatorInterface, WebFetcher, WebFetcherInterface
from .platform_detector import PlatformDetector, PlatformDetectorInterface
from .metadata_extractor import MetadataExtractor, MetadataExtractorInterface
from .cache_service import MetadataCache, CacheInterface
from .metadata_service import MetadataService

T = TypeVar('T')

class ServiceContainer:
    """Container for managing service dependencies with dependency injection"""

    def __init__(self):
        # Initialize services following dependency inversion principle
        self._services: Dict[Type, object] = {}

        # Register services in dependency order
        self._register_services()

    def _register_services(self) -> None:
        """Register all services with proper dependency injection"""
        # Register interfaces with their implementations
        self._services[URLValidatorInterface] = URLValidator()
        self._services[PlatformDetectorInterface] = PlatformDetector()

        # Services with dependencies
        self._services[WebFetcherInterface] = WebFetcher(
            self._services[URLValidatorInterface]
        )
        self._services[CacheInterface] = MetadataCache()
        self._services[MetadataExtractorInterface] = MetadataExtractor(
            self._services[PlatformDetectorInterface]
        )

        # Main service that depends on others
        self._services[MetadataService] = MetadataService(
            self._services[URLValidatorInterface],
            self._services[WebFetcherInterface],
            self._services[MetadataExtractorInterface],
            self._services[CacheInterface]
        )

    def get_metadata_service(self) -> MetadataService:
        """Get the metadata service instance"""
        return self._services[MetadataService]  # type: ignore

    def get_service(self, interface: Type[T]) -> T:
        """Generic method to retrieve a service by its interface"""
        service = self._services.get(interface)
        if service is None:
            raise ValueError(f"Service for interface {interface.__name__} not found")
        return service  # type: ignore