from abc import ABC, abstractmethod
from urllib.parse import urlparse


class PlatformDetectorInterface(ABC):
    """Interface for platform detection following the Dependency Inversion Principle"""

    @abstractmethod
    def detect_platform(self, url: str) -> str:
        """
        Detect the platform from a URL.

        Args:
            url: The URL string to analyze

        Returns:
            A string representing the detected platform name
        """
        pass


class PlatformDetector(PlatformDetectorInterface):
    """
    Detects the platform from a URL.
    This class identifies common platforms like Facebook, YouTube, Twitter, etc. based on the URL domain.
    """

    def detect_platform(self, url: str) -> str:
        """
        Detect platform based on URL domain.

        Args:
            url: The URL string to analyze

        Returns:
            A string representing the detected platform name or "Unknown" if not detected
        """
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
            "threads.com": "Threads",
            "medium.com": "Medium"
        }

        for platform_domain, platform_name in platform_mapping.items():
            if platform_domain in domain:
                return platform_name

        return "Unknown"