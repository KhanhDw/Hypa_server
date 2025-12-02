from abc import ABC, abstractmethod
import httpx
from fastapi import HTTPException
from app.services.url_validator import URLValidatorInterface

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
        if not self.url_validator.validate(url):
            raise HTTPException(status_code=400, detail="Invalid or unsafe URL provided")

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
                    raise HTTPException(status_code=400, detail="URL does not return HTML content")

                return res.text

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error occurred: {e}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=400, detail=f"Request error occurred: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")