from typing import Dict, Any
from app.services.url_validator import URLValidatorInterface
from app.services.web_fetcher import WebFetcherInterface
from app.services.metadata_extractor import MetadataExtractorInterface
from app.services.cache_service import CacheInterface
from app.core.models import Metadata
from fastapi import HTTPException

class MetadataService:
    """
    Main service for metadata operations following SOLID principles
    """
    
    def __init__(
        self,
        url_validator: URLValidatorInterface,
        web_fetcher: WebFetcherInterface,
        metadata_extractor: MetadataExtractorInterface,
        cache: CacheInterface
    ):
        self.url_validator = url_validator
        self.web_fetcher = web_fetcher
        self.metadata_extractor = metadata_extractor
        self.cache = cache

    async def get_metadata(self, url: str) -> Dict[str, Any]:
        """Get metadata for a URL with caching"""
        if not url:
            raise HTTPException(status_code=400, detail="URL parameter is required")
        
        if not self.url_validator.validate(url):
            raise HTTPException(status_code=400, detail="Invalid or unsafe URL provided")

        # Check cache first
        cached_data = self.cache.get(url)
        if cached_data:
            result = cached_data.to_dict()
            result["cached"] = True
            return result

        try:
            # Fetch and parse
            html = await self.web_fetcher.fetch_html(url)
            metadata = self.metadata_extractor.extract(html, url)

            # Save to cache
            self.cache.set(url, metadata)

            result = metadata.to_dict()
            result["cached"] = False
            return result
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            # Handle unexpected errors
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred while processing the URL: {e}")