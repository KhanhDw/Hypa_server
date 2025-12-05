from dataclasses import dataclass
from typing import Optional


@dataclass
class Metadata:
    """
    Represents metadata for a URL following the Open Graph protocol
    """
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    site_name: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    platform: Optional[str] = None
    author: Optional[str] = None
    published_time: Optional[str] = None
    modified_time: Optional[str] = None
    section: Optional[str] = None
    video: Optional[str] = None
    audio: Optional[str] = None
    locale: Optional[str] = None
    determiner: Optional[str] = None
    image_width: Optional[str] = None
    image_height: Optional[str] = None
    image_alt: Optional[str] = None
    video_width: Optional[str] = None
    video_height: Optional[str] = None
    twitter_card: Optional[str] = None
    twitter_site: Optional[str] = None
    twitter_creator: Optional[str] = None
    twitter_image: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    canonical_url: Optional[str] = None
    favicon: Optional[str] = None
    language: Optional[str] = None
    charset: Optional[str] = None
    cached: bool = False

    def to_dict(self) -> dict:
        """Convert the metadata to a dictionary representation"""
        return {
            "title": self.title,
            "description": self.description,
            "image": self.image,
            "site_name": self.site_name,
            "type": self.type,
            "url": self.url,
            "platform": self.platform,
            "author": self.author,
            "published_time": self.published_time,
            "modified_time": self.modified_time,
            "section": self.section,
            "video": self.video,
            "audio": self.audio,
            "locale": self.locale,
            "determiner": self.determiner,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "image_alt": self.image_alt,
            "video_width": self.video_width,
            "video_height": self.video_height,
            "twitter_card": self.twitter_card,
            "twitter_site": self.twitter_site,
            "twitter_creator": self.twitter_creator,
            "twitter_image": self.twitter_image,
            "twitter_title": self.twitter_title,
            "twitter_description": self.twitter_description,
            "canonical_url": self.canonical_url,
            "favicon": self.favicon,
            "language": self.language,
            "charset": self.charset,
            "cached": self.cached
        }