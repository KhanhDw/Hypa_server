import logging
import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from typing import Optional

import httpx


logger = logging.getLogger(__name__)


class URLValidatorInterface(ABC):
    """Interface for URL validation following the Dependency Inversion Principle"""

    @abstractmethod
    def validate(self, url: str) -> bool:
        """
        Validate a URL to check if it's safe and properly formatted.

        Args:
            url: The URL string to validate

        Returns:
            True if the URL is valid and safe, False otherwise
        """
        pass


class URLValidator(URLValidatorInterface):
    """
    Validates URLs and prevents SSRF attacks.
    This class implements URL validation logic to ensure URLs are safe to access.
    """

    def validate(self, url: str) -> bool:
        """
        Validate URL and check for potential SSRF attacks.

        Args:
            url: The URL string to validate

        Returns:
            True if the URL is valid and safe, False otherwise
        """
        try:
            parsed = urlparse(url)
            if not parsed.scheme or parsed.scheme not in ["http", "https"]:
                return False
            if not parsed.netloc:
                return False

            hostname = parsed.hostname or ""

            # Block internal IPs to prevent SSRF
            private_patterns = [
                r"^127\.0\.0\.1",
                r"^localhost",
                r"^10\.",
                r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",
                r"^192\.168\."
            ]
            for pattern in private_patterns:
                if re.match(pattern, hostname):
                    return False

            return True
        except Exception:
            return False


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
            raise ValueError("Invalid or unsafe URL provided")

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; LinkPreview/1.0)"
        }

        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                res = await client.get(url, headers=headers)
                res.raise_for_status()

                # Ensure content is HTML
                content_type = res.headers.get("content-type", "")
                if "text/html" not in content_type.lower():
                    logger.warning(f"URL does not return HTML content. Content-Type: {content_type}")
                    raise ValueError(f"Content type '{content_type}' is not supported")

                logger.info(f"Successfully fetched HTML content from URL: {url}")
                return res.text

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while fetching URL {url}: {e}")
            raise ValueError(f"HTTP error occurred: {e}")
        except httpx.RequestError as e:
            logger.error(f"Request error occurred while fetching URL {url}: {str(e)}")
            raise ValueError(f"Request error occurred: {str(e)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching URL {url}: {str(e)}")
            raise ValueError(f"An unexpected error occurred: {str(e)}")