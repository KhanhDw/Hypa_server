import re
from urllib.parse import urlparse
from abc import ABC, abstractmethod

class URLValidatorInterface(ABC):
    """Interface for URL validation following the Dependency Inversion Principle"""
    
    @abstractmethod
    def validate(self, url: str) -> bool:
        pass

class URLValidator(URLValidatorInterface):
    """
    Validates URLs and prevents SSRF attacks
    """
    
    def validate(self, url: str) -> bool:
        """Validate URL and check for potential SSRF attacks"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or parsed.scheme not in ["http", "https"]:
                return False
            if not parsed.netloc:
                return False

            hostname = parsed.hostname or ""

            # Block internal IPs to prevent SSRF
            private_patterns = [
                r"^127\.0\.0\.1",
                r"^localhost",
                r"^10\.",
                r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",
                r"^192\.168\."
            ]
            for pattern in private_patterns:
                if re.match(pattern, hostname):
                    return False

            return True
        except Exception:
            return False