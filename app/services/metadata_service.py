import logging
from typing import Dict, Any
from .fetcher import URLValidatorInterface, WebFetcherInterface
from .metadata_extractor import MetadataExtractorInterface
from .cache_service import CacheInterface
from app.core.models import Metadata
from fastapi import HTTPException
from .exceptions import URLValidationError, ServiceError

logger = logging.getLogger(__name__)

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
        """
        Get comprehensive metadata for a URL with caching.

        Args:
            url: The URL to extract metadata from

        Returns:
            Dictionary containing all extracted metadata fields

        Raises:
            HTTPException: If URL is invalid or processing fails
        """
        logger.info(f"Getting metadata for URL: {url}")

        if not url or not url.strip():
            logger.warning("Empty or whitespace-only URL parameter provided")
            raise HTTPException(status_code=400, detail="URL parameter is required")

        try:
            # Check cache first for performance
            cached_data = self.cache.get(url)
            if cached_data:
                logger.info(f"Metadata retrieved from cache for URL: {url}")
                result = cached_data.to_dict()
                result["cached"] = True
                return result

            logger.info(f"Metadata not in cache, fetching HTML for URL: {url}")
            # Fetch HTML content from URL
            html = await self.web_fetcher.fetch_html(url)

            logger.info(f"Extracting metadata from HTML for URL: {url}")
            # Extract comprehensive metadata from HTML
            metadata = self.metadata_extractor.extract(html, url)

            # Save to cache for future requests
            self.cache.set(url, metadata)
            logger.info(f"Metadata extracted and cached for URL: {url}")

            # Convert to dictionary and return with cache status
            result = metadata.to_dict()
            result["cached"] = False
            return result
        except URLValidationError as e:
            logger.warning(f"URL validation failed for URL {url}: {e.message}")
            # Convert URL validation errors to HTTP exceptions
            raise HTTPException(status_code=400, detail=e.message)
        except ServiceError as e:
            logger.error(f"Service error occurred while processing URL {url}: {e.message}")
            # Convert service errors to HTTP exceptions
            raise HTTPException(status_code=500, detail=e.message)
        except Exception as e:
            logger.error(f"Unexpected error occurred while processing URL {url}: {str(e)}")
            # Handle unexpected errors gracefully
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred while processing the URL: {str(e)}"
            )