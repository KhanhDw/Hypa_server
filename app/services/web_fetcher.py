import logging
from abc import ABC, abstractmethod
import httpx
from app.services.url_validator import URLValidatorInterface
from .exceptions import URLValidationError, HTTPFetchError, UnsupportedContentTypeError

# Import settings
from app.core.config import settings

logger = logging.getLogger(__name__)

class WebFetcherInterface(ABC):
    """Interface for fetching web content following the Dependency Inversion Principle"""

    @abstractmethod
    async def fetch_html(self, url: str) -> str:
        pass

class WebFetcher(WebFetcherInterface):
    """
    Fetches HTML content from URLs safely
    """

    def __init__(self, url_validator: URLValidatorInterface):
        self.url_validator = url_validator

    async def fetch_html(self, url: str) -> str:
        """Fetch HTML content from a URL with validation"""
        logger.info(f"Fetching HTML content from URL: {url}")

        if not self.url_validator.validate(url):
            logger.warning(f"Invalid or unsafe URL provided: {url}")
            raise URLValidationError("Invalid or unsafe URL provided")

        headers = {
            "User-Agent": settings.fetch_user_agent
        }

        try:
            async with httpx.AsyncClient(timeout=settings.fetch_timeout, follow_redirects=settings.fetch_follow_redirects) as client:
                res = await client.get(url, headers=headers)
                res.raise_for_status()

                # Ensure content is HTML
                content_type = res.headers.get("content-type", "")
                if "text/html" not in content_type.lower():
                    logger.warning(f"URL does not return HTML content. Content-Type: {content_type}")
                    raise UnsupportedContentTypeError(content_type)

                logger.info(f"Successfully fetched HTML content from URL: {url}")
                return res.text

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while fetching URL {url}: {e}")
            raise HTTPFetchError(status_code=e.response.status_code, message=f"HTTP error occurred: {e}")
        except httpx.RequestError as e:
            logger.error(f"Request error occurred while fetching URL {url}: {str(e)}")
            raise HTTPFetchError(status_code=400, message=f"Request error occurred: {str(e)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching URL {url}: {str(e)}")
            raise HTTPFetchError(status_code=500,message=f"An unexpected error occurred: {str(e)}")