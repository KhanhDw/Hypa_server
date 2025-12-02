from abc import ABC, abstractmethod
from urllib.parse import urlparse

class PlatformDetectorInterface(ABC):
    """Interface for platform detection following the Dependency Inversion Principle"""
    
    @abstractmethod
    def detect_platform(self, url: str) -> str:
        pass

class PlatformDetector(PlatformDetectorInterface):
    """
    Detects the platform from a URL
    """
    
    def detect_platform(self, url: str) -> str:
        """Detect platform based on URL domain"""
        domain = urlparse(url).netloc.lower()

        platform_mapping = {
            "facebook.com": "Facebook",
            "instagram.com": "Instagram", 
            "tiktok.com": "TikTok",
            "youtube.com": "YouTube",
            "youtu.be": "YouTube",
            "twitter.com": "X/Twitter",
            "x.com": "X/Twitter",
            "reddit.com": "Reddit",
            "linkedin.com": "LinkedIn",
            "threads.com": "Threads"
        }

        for platform_domain, platform_name in platform_mapping.items():
            if platform_domain in domain:
                return platform_name

        return "Unknown"