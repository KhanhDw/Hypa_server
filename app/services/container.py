from app.services.url_validator import URLValidator
from app.services.web_fetcher import WebFetcher
from app.services.platform_detector import PlatformDetector
from app.services.metadata_extractor import MetadataExtractor
from app.services.cache_service import MetadataCache
from app.services.metadata_service import MetadataService


class ServiceContainer:
    """Container for managing service dependencies"""
    
    def __init__(self):
        self.url_validator = URLValidator()
        self.platform_detector = PlatformDetector()
        self.web_fetcher = WebFetcher(self.url_validator)
        self.metadata_extractor = MetadataExtractor(self.platform_detector)
        self.cache = MetadataCache()
        self.metadata_service = MetadataService(
            self.url_validator,
            self.web_fetcher,
            self.metadata_extractor,
            self.cache
        )
    
    def get_metadata_service(self):
        return self.metadata_service