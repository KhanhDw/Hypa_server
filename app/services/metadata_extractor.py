import logging
from abc import ABC, abstractmethod
from typing import Optional

from .description_extractor import DescriptionExtractor
from .html_parser import HTMLParser
from app.core.models import Metadata
from .platform_detector import PlatformDetectorInterface


logger = logging.getLogger(__name__)


class MetadataExtractorInterface(ABC):
    """Interface for metadata extraction following the Dependency Inversion Principle"""

    @abstractmethod
    def extract(self, html: str, url: str) -> Metadata:
        pass


class MetadataExtractor(MetadataExtractorInterface):
    """
    Extracts comprehensive metadata from HTML following Open Graph protocol and other standards
    """

    def __init__(self, platform_detector: PlatformDetectorInterface):
        self.platform_detector: PlatformDetectorInterface = platform_detector

    def extract(self, html: str, url: str) -> Metadata:
        """Extract comprehensive metadata from HTML content"""
        logger.info(f"Extracting metadata from HTML for URL: {url}")

        try:
            # Parse HTML content
            html_parser = HTMLParser(html, url)

            # Detect platform
            platform = self.platform_detector.detect_platform(url)

            # Extract basic metadata
            title = html_parser.get_title()
            image = html_parser.get_image()
            site_name = html_parser.get_meta_content("og:site_name") or html_parser.get_meta_content("application-name")
            og_type = html_parser.get_meta_content("og:type")
            og_url = html_parser.get_meta_content("og:url") or url

            # Extract description using the multi-stage fallback pipeline
            description_extractor = DescriptionExtractor(html, url, platform)
            description = description_extractor.extract_description()

            # Get extended metadata
            extended_og_data = html_parser.get_extended_og_data()
            twitter_data = html_parser.get_twitter_data()
            canonical_url = html_parser.get_canonical_url()
            favicon = html_parser.get_favicon()
            language = html_parser.get_language()
            charset = html_parser.get_charset()

            # Combine all metadata into a single Metadata object
            metadata = Metadata(
                title=title,
                description=description,
                image=image,
                site_name=site_name or self._get_site_name_from_url(url),
                type=og_type,
                url=og_url,
                platform=platform,
                author=extended_og_data.get("author"),
                published_time=extended_og_data.get("published_time"),
                modified_time=extended_og_data.get("modified_time"),
                section=extended_og_data.get("section"),
                video=extended_og_data.get("video"),
                audio=html_parser.get_meta_content("og:audio"),
                locale=extended_og_data.get("locale"),
                determiner=extended_og_data.get("determiner"),
                image_width=extended_og_data.get("image_width"),
                image_height=extended_og_data.get("image_height"),
                image_alt=extended_og_data.get("image_alt"),
                video_width=extended_og_data.get("video_width"),
                video_height=extended_og_data.get("video_height"),
                twitter_card=twitter_data.get("twitter_card"),
                twitter_site=twitter_data.get("twitter_site"),
                twitter_creator=twitter_data.get("twitter_creator"),
                twitter_image=twitter_data.get("twitter_image"),
                twitter_title=twitter_data.get("twitter_title"),
                twitter_description=twitter_data.get("twitter_description"),
                canonical_url=canonical_url,
                favicon=favicon,
                language=language,
                charset=charset
            )

            logger.info(f"Successfully extracted metadata for URL: {url}")
            return metadata
        except Exception as e:
            logger.error(f"Failed to extract metadata for URL {url}: {str(e)}")
            # Handle any parsing errors gracefully
            return Metadata(
                title=None,
                description=None,
                image=None,
                site_name=self._get_site_name_from_url(url),
                type=None,
                url=url,
                platform=self.platform_detector.detect_platform(url)
            )

    def _get_site_name_from_url(self, url: str) -> str:
        """Extract site name from URL if not available in metadata"""
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        return parsed_url.netloc