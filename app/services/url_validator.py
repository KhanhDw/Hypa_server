import re
from urllib.parse import urlparse
from abc import ABC, abstractmethod

class URLValidatorInterface(ABC):
    """Interface for URL validation following the Dependency Inversion Principle"""

    @abstractmethod
    def validate(self, url: str) -> bool:
        """
        Validate a URL to check if it's safe and properly formatted.

        Args:
            url: The URL string to validate

        Returns:
            True if the URL is valid and safe, False otherwise
        """
        pass

class URLValidator(URLValidatorInterface):
    """
    Validates URLs and prevents SSRF attacks.
    This class implements URL validation logic to ensure URLs are safe to access.
    """

    def validate(self, url: str) -> bool:
        """
        Validate URL and check for potential SSRF attacks.

        Args:
            url: The URL string to validate

        Returns:
            True if the URL is valid and safe, False otherwise
        """
        try:
            parsed = urlparse(url)
            if not parsed.scheme or parsed.scheme not in ["http", "https"]:
                return False
            if not parsed.netloc:
                return False

            # Check port validity
            if parsed.port is not None:
                if parsed.port < 1 or parsed.port > 65535:
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