"""Metadata extraction utilities for extracting various metadata types"""

import logging
from typing import  Dict, Any
from urllib.parse import urlparse
from .html_parser import HTMLParser

logger = logging.getLogger(__name__)

class BasicMetadataExtractor:
    """Extracts basic Open Graph and Twitter Card metadata"""

    def __init__(self, html_parser: HTMLParser, url: str):
        self.html_parser = html_parser
        self.url = url
        self.parsed_url = urlparse(url)

    def extract(self) -> Dict[str, Any]:
        """Extract basic metadata fields"""
        logger.debug(f"Extracting basic metadata for URL: {self.url}")

        return {
            "title": self.html_parser.get_title(),
            "description": self.html_parser.get_description(),
            "image": self.html_parser.get_image(),
            "site_name": self.html_parser.get_meta_content("og:site_name") or
                        self.html_parser.get_meta_content("application-name") or
                        self.parsed_url.netloc,
            "type": self.html_parser.get_meta_content("og:type"),
            "url": self.html_parser.get_meta_content("og:url") or self.url
        }