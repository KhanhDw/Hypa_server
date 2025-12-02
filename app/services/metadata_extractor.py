from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Optional
from app.core.models import Metadata

# Interface for platform detector - should be imported from appropriate location
from app.services.platform_detector import PlatformDetectorInterface

class MetadataExtractorInterface(ABC):
    """Interface for metadata extraction following the Dependency Inversion Principle"""

    @abstractmethod
    def extract(self, html: str, url: str) -> Metadata:
        pass

class MetadataExtractor(MetadataExtractorInterface):
    """
    Extracts metadata from HTML following Open Graph protocol
    """

    def __init__(self, platform_detector: PlatformDetectorInterface):
        self.platform_detector: PlatformDetectorInterface = platform_detector

    def extract(self, html: str, url: str) -> Metadata:
        """Extract metadata from HTML content"""
        try:
            soup = BeautifulSoup(html, "lxml")

            def get_meta(tag: str) -> Optional[str]:
                el = soup.find("meta", property=tag) or soup.find("meta", attrs={"name": tag})
                if el and el.get("content"):
                    content = el.get("content")
                    # Handle cases where content might be a list or other type
                    if isinstance(content, list):
                        return str(content[0]) if content else None
                    else:
                        return str(content) if content else None
                return None

            title = get_meta("og:title")
            if not title:
                # Safely handle cases where <title> or its .string may be None
                if soup.title and soup.title.string:
                    # Ensure title.string is not None before stripping
                    title_content = soup.title.string
                    if title_content:
                        t = str(title_content).strip()
                        title = t if t else None
                    else:
                        title = None
                else:
                    title = None

            description = get_meta("og:description") or get_meta("description")
            image = get_meta("og:image") or get_meta("twitter:image")

            # Fallback: get first image from <img> if OG image doesn't exist
            if not image:
                img_tag = soup.find("img")
                if img_tag and img_tag.get("src"):
                    src_val = img_tag.get("src")
                    if isinstance(src_val, list):
                        image = str(src_val[0]) if src_val else None
                    else:
                        image = str(src_val) if src_val else None

            site_name = get_meta("og:site_name") or urlparse(url).netloc
            type_ = get_meta("og:type")
            platform = self.platform_detector.detect_platform(url)

            return Metadata(
                title=title,
                description=description,
                image=image,
                site_name=site_name,
                type=type_,
                url=url,
                platform=platform
            )
        except Exception:
            # Handle any parsing errors gracefully
            return Metadata(
                title=None,
                description=None,
                image=None,
                site_name=urlparse(url).netloc,
                type=None,
                url=url,
                platform=self.platform_detector.detect_platform(url)
            )