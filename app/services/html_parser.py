"""HTML parsing utilities for metadata extraction"""

import json
import logging
import re
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class HTMLParser:
    """Encapsulates HTML parsing functionality"""
    
    def __init__(self, html: str, url: str):
        """
        Initialize the HTML parser
        
        Args:
            html: HTML content to parse
            url: Base URL for resolving relative links
        """
        self.html = html
        self.url = url
        self.soup = BeautifulSoup(html, "lxml")
    
    def get_meta_content(self, tag: str, property_attr: str = "property") -> Optional[str]:
        """Helper function to extract meta tag content"""
        try:
            el = self.soup.find("meta", {property_attr: tag}) or self.soup.find("meta", attrs={"name": tag})
            if el and el.get("content"):
                content = el.get("content")
                # Handle cases where content might be a list or other type
                if isinstance(content, list):
                    return str(content[0]) if content else None
                else:
                    return str(content) if content else None
        except Exception as e:
            # Log the specific error for better debugging
            logger.warning(f"Failed to extract meta tag '{tag}': {str(e)}")
        return None

    def get_meta_list(self, tag: str, separator: str = ",") -> Optional[List[str]]:
        """Helper function to extract a list of values from a tag"""
        try:
            content = self.get_meta_content(tag)
            if content:
                # Split by common separators and clean up
                values = [item.strip() for item in content.split(separator) if item.strip()]
                if values:
                    return values
        except Exception as e:
            # Log the specific error for better debugging
            logger.warning(f"Failed to extract meta list '{tag}': {str(e)}")
        return None
    
    def get_title(self) -> Optional[str]:
        """Extract title from multiple possible sources"""
        # Try Open Graph, Twitter, or regular title meta tags first
        title = self.get_meta_content("og:title") or \
                self.get_meta_content("twitter:title") or \
                self.get_meta_content("title")
        
        if not title:
            # Fallback to HTML title tag
            try:
                if self.soup.title and self.soup.title.string:
                    title_content = self.soup.title.string
                    if title_content:
                        t = str(title_content).strip()
                        title = t if t else None
            except Exception:
                logger.debug("Failed to extract title from HTML title tag")
                title = None
        
        return title
    
    def get_description(self) -> Optional[str]:
        """Extract description from multiple possible sources"""
        return self.get_meta_content("og:description") or \
               self.get_meta_content("twitter:description") or \
               self.get_meta_content("description")
    
    def get_image(self) -> Optional[str]:
        """Extract image from multiple possible sources"""
        image = self.get_meta_content("og:image") or \
                self.get_meta_content("twitter:image") or \
                self.get_meta_content("image")
        
        if not image:
            # Fallback: get first image from <img> if OG image doesn't exist
            try:
                img_tag = self.soup.find("img")
                if img_tag and img_tag.get("src"):
                    src_val = img_tag.get("src")
                    if isinstance(src_val, list):
                        raw_image = str(src_val[0]) if src_val else None
                    else:
                        raw_image = str(src_val) if src_val else None
                    # Make relative URLs absolute
                    if raw_image:
                        image = urljoin(self.url, raw_image)
            except Exception as e:
                logger.warning(f"Failed to extract image from img tag: {str(e)}")
        
        return image
    
    def get_canonical_url(self) -> Optional[str]:
        """Extract canonical URL"""
        canonical_url = None
        try:
            canonical_tag = self.soup.find("link", rel="canonical")
            if canonical_tag and canonical_tag.get("href"):
                canonical_href = canonical_tag.get("href")
                if canonical_href:
                    canonical_url = urljoin(self.url, str(canonical_href))
        except Exception as e:
            logger.warning(f"Failed to extract canonical URL: {str(e)}")
        
        return canonical_url
    
    def get_favicon(self) -> Optional[str]:
        """Extract favicon"""
        favicon = None
        try:
            favicon_tag = self.soup.find("link", rel=lambda x: x and "icon" in x.lower())
            if favicon_tag and favicon_tag.get("href"):
                favicon_href = favicon_tag.get("href")
                if favicon_href:
                    favicon = urljoin(self.url, str(favicon_href))
        except Exception as e:
            logger.warning(f"Failed to extract favicon link: {str(e)}")
        
        return favicon
    
    def get_language(self) -> Optional[str]:
        """Extract language"""
        language = None
        try:
            language = self.soup.get("lang") or (self.soup.find("html") or {}).get("lang")
        except Exception as e:
            logger.warning(f"Failed to extract language: {str(e)}")
        
        return language
    
    def get_charset(self) -> Optional[str]:
        """Extract charset"""
        charset = None
        try:
            charset_meta = self.soup.find("meta", attrs={"charset": True})
            if charset_meta:
                charset = charset_meta.get("charset")
            else:
                charset_meta = self.soup.find("meta", attrs={"content": lambda x: x and "charset=" in str(x).lower()})
                if charset_meta:
                    content = charset_meta.get("content", "")
                    if "charset=" in str(content).lower():
                        charset = str(content).split("charset=")[1].split(";")[0].strip()
        except Exception as e:
            logger.warning(f"Failed to extract charset: {str(e)}")
        
        return charset

    def get_video_url(self) -> Optional[str]:
        """Extract video URL from meta tags"""
        return self.get_meta_content("og:video") or \
               self.get_meta_content("og:video:url")

    def get_twitter_data(self) -> Dict[str, str]:
        """Extract all Twitter Card metadata"""
        return {
            "twitter_card": self.get_meta_content("twitter:card", "name"),
            "twitter_site": self.get_meta_content("twitter:site", "name"),
            "twitter_creator": self.get_meta_content("twitter:creator", "name"),
            "twitter_image": self.get_meta_content("twitter:image", "name"),
            "twitter_title": self.get_meta_content("twitter:title", "name"),
            "twitter_description": self.get_meta_content("twitter:description", "name")
        }

    def get_extended_og_data(self) -> Dict[str, str]:
        """Extract extended Open Graph metadata"""
        return {
            "type": self.get_meta_content("og:type"),
            "site_name": self.get_meta_content("og:site_name"),
            "locale": self.get_meta_content("og:locale"),
            "determiner": self.get_meta_content("og:determiner"),
            "image_width": self.get_meta_content("og:image:width"),
            "image_height": self.get_meta_content("og:image:height"),
            "image_alt": self.get_meta_content("og:image:alt"),
            "video": self.get_meta_content("og:video"),
            "video_url": self.get_meta_content("og:video:url"),
            "video_width": self.get_meta_content("og:video:width"),
            "video_height": self.get_meta_content("og:video:height"),
            "author": self.get_meta_content("article:author") or self.get_meta_content("author"),
            "published_time": self.get_meta_content("article:published_time"),
            "modified_time": self.get_meta_content("article:modified_time"),
            "section": self.get_meta_content("article:section"),
        }

    def get_json_ld_data(self) -> List[Dict[str, Any]]:
        """Extract JSON-LD structured data"""
        json_ld_data = []
        try:
            scripts = self.soup.find_all("script", type="application/ld+json")
            for script in scripts:
                if script.string:
                    try:
                        json_obj = json.loads(script.string)
                        if isinstance(json_obj, list):
                            json_ld_data.extend(json_obj)
                        elif isinstance(json_obj, dict):
                            json_ld_data.append(json_obj)
                    except json.JSONDecodeError as json_error:
                        logger.warning(f"Failed to parse JSON-LD script: {str(json_error)}")
                        continue
        except Exception as e:
            logger.warning(f"Error extracting JSON-LD data: {str(e)}")
        
        return json_ld_data