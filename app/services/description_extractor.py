import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class DescriptionExtractor:
    """Extracts full descriptions from various sources with fallbacks"""

    def __init__(self, html: str, url: str, platform: str):
        self.html = html
        self.url = url
        self.platform = platform
        self.soup = BeautifulSoup(html, "lxml")

    def extract_description(self) -> Optional[str]:
        """
        Extract description using multi-stage fallback pipeline
        """
        # Stage 1: Check if existing meta description is sufficient
        og_desc = self._get_meta_content("og:description")
        twitter_desc = self._get_meta_content("twitter:description", "name")
        meta_desc = self._get_meta_content("description")

        # If any of these are good descriptions, use them
        for desc in [og_desc, twitter_desc, meta_desc]:
            if desc and self._is_sufficient_description(desc):
                return desc

        # Stage 2: Extract from platform-specific sources
        platform_desc = self._extract_platform_description()
        if platform_desc and self._is_sufficient_description(platform_desc):
            return platform_desc

        # Stage 3: Extract from article tags
        article_desc = self._extract_article_description()
        if article_desc and self._is_sufficient_description(article_desc):
            return article_desc

        # Stage 4: Extract from longest paragraph
        paragraph_desc = self._extract_paragraph_description()
        if paragraph_desc and self._is_sufficient_description(paragraph_desc):
            return paragraph_desc

        # Stage 5: Extract from main content
        main_desc = self._extract_main_description()
        if main_desc and self._is_sufficient_description(main_desc):
            return main_desc

        # Fallback: Use the best available description even if it's not ideal
        for desc in [og_desc, twitter_desc, meta_desc]:
            if desc:
                return desc

        return None

    def _is_sufficient_description(self, desc: str) -> bool:
        """
        Check if description is sufficient (not truncated or too short)
        """
        if not desc:
            return False

        # Check if it contains ellipsis indicating truncation
        if "..." in desc or "…" in desc:
            return False

        # Check if it's too short
        if len(desc.strip()) < 50:
            return False

        return True

    def _get_meta_content(self, tag: str, property_attr: str = "property") -> Optional[str]:
        """Helper function to extract meta tag content"""
        try:
            el = self.soup.find("meta", {property_attr: tag}) or self.soup.find("meta", attrs={"name": tag})
            if el and el.get("content"):
                content = el.get("content")
                if isinstance(content, list):
                    return str(content[0]) if content else None
                else:
                    return str(content) if content else None
        except Exception:
            logger.debug(f"Failed to extract meta tag: {tag}")
            pass
        return None

    def _extract_platform_description(self) -> Optional[str]:
        """
        Extract description from platform-specific sources
        """
        if self.platform == "Facebook" or self.platform == "Instagram":
            return self._extract_facebook_instagram_description()
        elif self.platform == "X/Twitter":
            return self._extract_twitter_description()
        elif self.platform == "TikTok":
            return self._extract_tiktok_description()
        elif self.platform == "YouTube":
            return self._extract_youtube_description()
        elif self.platform == "LinkedIn":
            return self._extract_linkedin_description()
        elif self.platform == "Medium":
            return self._extract_medium_description()
        else:
            # Generic JSON-LD extraction for other platforms
            return self._extract_json_ld_description()

    def _extract_facebook_instagram_description(self) -> Optional[str]:
        """
        Extract description from Facebook/Instagram JSON scripts
        """
        try:
            # Look for JSON in script tags
            scripts = self.soup.find_all("script", type="application/json")
            for script in scripts:
                try:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, dict):
                        # Try to find description in common fields
                        for key in ["description", "desc", "text", "caption"]:
                            if key in json_data and json_data[key]:
                                return str(json_data[key])
                except (json.JSONDecodeError, TypeError):
                    continue

            # Look for any script that might contain JSON
            scripts = self.soup.find_all("script", string=re.compile(r"\{.*\}"))
            for script in scripts:
                script_text = script.string
                if script_text:
                    # Find JSON objects in the script
                    matches = re.findall(r'(\{[^{}]*\}|\[[^\[\]]*\])', script_text)
                    for match in matches:
                        try:
                            json_obj = json.loads(match)
                            if isinstance(json_obj, dict):
                                for key in ["description", "desc", "text", "caption", "message"]:
                                    if key in json_obj and json_obj[key]:
                                        return str(json_obj[key])
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.debug(f"Error extracting Facebook/Instagram description: {e}")

        return None

    def _extract_twitter_description(self) -> Optional[str]:
        """
        Extract description from Twitter/X JSON-LD and scripts
        """
        try:
            # First, try JSON-LD
            json_ld_scripts = self.soup.find_all("script", type="application/ld+json")
            for script in json_ld_scripts:
                try:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, list):
                        for item in json_data:
                            if isinstance(item, dict):
                                if "description" in item and item["description"]:
                                    return str(item["description"])
                                elif "text" in item and item["text"]:
                                    return str(item["text"])
                    elif isinstance(json_data, dict):
                        if "description" in json_data and json_data["description"]:
                            return str(json_data["description"])
                        elif "text" in json_data and json_data["text"]:
                            return str(json_data["text"])
                except (json.JSONDecodeError, TypeError):
                    continue

            # Look for any script that might contain tweet text
            scripts = self.soup.find_all("script", string=re.compile(r"tweet|text"))
            for script in scripts:
                script_text = script.string
                if script_text:
                    # Try to find description in common Twitter JSON structures
                    matches = re.findall(r'"text"[^,}]*:[^,}]*["\']([^"\']+)["\']', script_text)
                    for match in matches:
                        if len(match) > 50:  # Only return if it's reasonably long
                            return match
        except Exception as e:
            logger.debug(f"Error extracting Twitter description: {e}")

        return None

    def _extract_tiktok_description(self) -> Optional[str]:
        """
        Extract description from TikTok JSON scripts
        """
        try:
            # Look for JSON in script tags
            scripts = self.soup.find_all("script", type="application/json")
            for script in scripts:
                try:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, dict):
                        # Look for common TikTok description fields
                        for key in ["desc", "description", "shareMeta", "title"]:
                            if key in json_data:
                                if isinstance(json_data[key], str) and json_data[key]:
                                    return json_data[key]
                                elif isinstance(json_data[key], dict) and "text" in json_data[key]:
                                    return str(json_data[key]["text"])
                except (json.JSONDecodeError, TypeError):
                    continue

            # Look for any script that might contain TikTok data
            scripts = self.soup.find_all("script")
            for script in scripts:
                script_text = script.string
                if script_text and ("tiktok" in script_text.lower() or "desc" in script_text.lower()):
                    # Find description patterns
                    matches = re.findall(r'["\']desc["\'][^}]*["\']([^"\']+)["\']', script_text)
                    for match in matches:
                        if len(match) > 10:  # Reasonable minimum length
                            return match
        except Exception as e:
            logger.debug(f"Error extracting TikTok description: {e}")

        return None

    def _extract_youtube_description(self) -> Optional[str]:
        """
        Extract description from YouTube JSON scripts
        """
        try:
            # YouTube often has JSON in script tags with player config
            scripts = self.soup.find_all("script")
            for script in scripts:
                if script.string:
                    # Look for YouTube-specific JSON patterns
                    matches = re.findall(r'(["\']shortDescription["\'][^}]*["\']([^"\']+)["\'])|(["\']description["\'][^}]*["\']([^"\']+)["\'])', script.string)
                    for match in matches:
                        desc = match[1] or match[3]  # Get the description from either pattern
                        if desc and len(desc) > 50:
                            return desc

            # Look for JSON-LD specifically
            json_ld_scripts = self.soup.find_all("script", type="application/ld+json")
            for script in json_ld_scripts:
                try:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, dict):
                        # YouTube JSON-LD has specific structure
                        if "@type" in json_data and json_data["@type"] == "VideoObject":
                            if "description" in json_data and json_data["description"]:
                                return str(json_data["description"])
                except (json.JSONDecodeError, TypeError):
                    continue
        except Exception as e:
            logger.debug(f"Error extracting YouTube description: {e}")

        return None

    def _extract_linkedin_description(self) -> Optional[str]:
        """
        Extract description from LinkedIn JSON scripts
        """
        try:
            # Look for LinkedIn-specific JSON-LD or scripts
            scripts = self.soup.find_all("script", type="application/json")
            for script in scripts:
                try:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, dict):
                        # Look for LinkedIn description fields
                        for key in ["description", "text"]:
                            if key in json_data and json_data[key]:
                                return str(json_data[key])
                        # Look for more specific fields
                        for key in ["com.linkedin", "article", "post", "summary"]:
                            if key in json_data:
                                if isinstance(json_data[key], str):
                                    return json_data[key]
                                elif isinstance(json_data[key], dict) and "description" in json_data[key]:
                                    return str(json_data[key]["description"])
                except (json.JSONDecodeError, TypeError):
                    continue
        except Exception as e:
            logger.debug(f"Error extracting LinkedIn description: {e}")

        return None

    def _extract_medium_description(self) -> Optional[str]:
        """
        Extract description from Medium articles
        """
        try:
            # Medium articles have their content in article tags
            article_tag = self.soup.find("article")
            if article_tag:
                # Get the text content of the first paragraph or the first section
                first_p = article_tag.find("p")
                if first_p and first_p.get_text():
                    text = first_p.get_text().strip()
                    if len(text) > 50:
                        return text

            # Fallback: look for JSON with article content
            scripts = self.soup.find_all("script", type="application/json")
            for script in scripts:
                try:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, dict):
                        # Look for content in common Medium JSON fields
                        for key in ["content", "text", "body", "postContent"]:
                            if key in json_data and json_data[key]:
                                content = json_data[key]
                                if isinstance(content, str):
                                    return content[:500]  # Limit to reasonable length
                                elif isinstance(content, list):
                                    # Try to join text elements from the array
                                    text_parts = [item for item in content if isinstance(item, str)]
                                    if text_parts:
                                        full_text = " ".join(text_parts)
                                        if len(full_text) > 50:
                                            return full_text[:500]
                except (json.JSONDecodeError, TypeError):
                    continue
        except Exception as e:
            logger.debug(f"Error extracting Medium description: {e}")

        return None

    def _extract_json_ld_description(self) -> Optional[str]:
        """
        Extract description from generic JSON-LD scripts
        """
        try:
            json_ld_scripts = self.soup.find_all("script", type="application/ld+json")
            for script in json_ld_scripts:
                try:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, list):
                        for item in json_data:
                            if isinstance(item, dict) and "description" in item and item["description"]:
                                desc = str(item["description"])
                                if len(desc) > 50:
                                    return desc
                    elif isinstance(json_data, dict):
                        if "description" in json_data and json_data["description"]:
                            desc = str(json_data["description"])
                            if len(desc) > 50:
                                return desc
                except (json.JSONDecodeError, TypeError):
                    continue
        except Exception as e:
            logger.debug(f"Error extracting JSON-LD description: {e}")

        return None

    def _extract_article_description(self) -> Optional[str]:
        """
        Extract description from article tags
        """
        try:
            article_tag = self.soup.find("article")
            if article_tag:
                # Remove script and style elements
                for script in article_tag(["script", "style"]):
                    script.decompose()

                # Get text and clean it
                text = article_tag.get_text()
                # Normalize whitespace
                text = " ".join(text.split())
                
                # Return a reasonable length description
                if len(text) > 50:
                    return text[:2000]  # Limit to 2000 chars max
        except Exception as e:
            logger.debug(f"Error extracting article description: {e}")

        return None

    def _extract_paragraph_description(self) -> Optional[str]:
        """
        Extract description from the longest paragraph
        """
        try:
            paragraphs = self.soup.find_all("p")
            longest_paragraph = ""
            
            for p in paragraphs:
                # Remove script and style elements
                for script in p(["script", "style"]):
                    script.decompose()
                
                text = p.get_text().strip()
                # Only consider paragraphs that are reasonably long
                if len(text) > len(longest_paragraph) and len(text) > 20:
                    longest_paragraph = text
            
            # Normalize whitespace
            if longest_paragraph:
                longest_paragraph = " ".join(longest_paragraph.split())
                if len(longest_paragraph) > 50:
                    return longest_paragraph[:1000]  # Limit to 1000 chars max
        except Exception as e:
            logger.debug(f"Error extracting paragraph description: {e}")

        return None

    def _extract_main_description(self) -> Optional[str]:
        """
        Extract description from main content area
        """
        try:
            # Look for main content areas
            main_content = self.soup.find("main") or self.soup.find("div", {"id": "content"}) or self.soup.find("div", {"class": "content"})
            
            if main_content:
                # Remove unwanted elements
                for elem in main_content(["script", "style", "nav", "header", "footer", "aside"]):
                    elem.decompose()
                
                text = main_content.get_text()
                # Normalize whitespace
                text = " ".join(text.split())
                
                if len(text) > 50:
                    return text[:1500]  # Limit to 1500 chars max
        except Exception as e:
            logger.debug(f"Error extracting main description: {e}")

        return None