import pytest
from app.services.url_validator import URLValidator


class TestURLValidator:
    """Unit tests for URLValidator"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.validator = URLValidator()

    @pytest.mark.parametrize("url,expected", [
        ("https://www.example.com", True),
        ("http://www.example.com", True),
        ("https://example.com", True),
        ("http://example.com", True),
        ("https://subdomain.example.com", True),
    ])
    def test_valid_urls(self, url, expected):
        """Test that valid URLs return True."""
        assert self.validator.validate(url) == expected

    @pytest.mark.parametrize("url,expected", [
        ("", False),
        ("not-a-url", False),
        ("ftp://example.com", False),
        ("javascript:alert('xss')", False),
        ("//example.com", False),
        ("https://", False),
        ("http://", False),
        ("", False),
    ])
    def test_invalid_urls(self, url, expected):
        """Test that invalid URLs return False."""
        assert self.validator.validate(url) == expected

    @pytest.mark.parametrize("url,expected", [
        ("http://127.0.0.1", False),
        ("http://localhost", False),
        ("http://10.0.0.1", False),
        ("http://172.16.0.1", False),
        ("http://192.168.1.1", False),
        ("https://127.0.0.1:8080", False),
        ("https://localhost/path", False),
    ])
    def test_private_ip_blocking(self, url, expected):
        """Test that private IPs are blocked to prevent SSRF."""
        assert self.validator.validate(url) == expected

    def test_malformed_url(self):
        """Test that malformed URLs return False."""
        assert self.validator.validate("http://[::1]:65536") is False
        assert self.validator.validate("http://example.com:999999") is False