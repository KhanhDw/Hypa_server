from typing import Optional, Dict, Any
from dataclasses import dataclass

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
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert the metadata to a dictionary representation"""
        return {
            "title": self.title,
            "description": self.description,
            "image": self.image,
            "site_name": self.site_name,
            "type": self.type,
            "url": self.url,
            "platform": self.platform,
            "cached": self.cached
        }