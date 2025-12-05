import pytest
from app.services.html_parser import HTMLParser


class TestHTMLParser:
    """Unit tests for HTMLParser"""

    def test_get_title_from_og_title(self):
        """Test extracting title from og:title meta tag."""
        # Arrange
        html = """
        <html>
        <head>
            <meta property="og:title" content="Open Graph Title">
            <title>Regular Title</title>
        </head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_title()

        # Assert
        assert result == "Open Graph Title"

    def test_get_title_from_regular_title(self):
        """Test extracting title from regular title tag when og:title not present."""
        # Arrange
        html = """
        <html>
        <head>
            <title>Regular Title</title>
        </head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_title()

        # Assert
        assert result == "Regular Title"

    def test_get_description(self):
        """Test extracting description from meta tags."""
        # Arrange
        html = """
        <html>
        <head>
            <meta property="og:description" content="Open Graph Description">
            <meta name="description" content="Regular Description">
        </head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act & Assert
        # Should prefer og:description
        result = parser.get_description()
        assert result == "Open Graph Description"

    def test_get_image_from_og_image(self):
        """Test extracting image from og:image meta tag."""
        # Arrange
        html = """
        <html>
        <head>
            <meta property="og:image" content="https://example.com/image.jpg">
        </head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_image()

        # Assert
        assert result == "https://example.com/image.jpg"

    def test_get_image_from_img_tag_fallback(self):
        """Test extracting image from img tag when og:image not present."""
        # Arrange
        html = """
        <html>
        <head></head>
        <body>
            <img src="/path/to/image.jpg" alt="An image">
        </body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_image()

        # Assert
        # Should resolve relative URL to absolute
        assert result == "https://example.com/path/to/image.jpg"

    def test_get_meta_content_existing(self):
        """Test extracting content from existing meta tag."""
        # Arrange
        html = """
        <html>
        <head>
            <meta property="og:site_name" content="Example Site">
        </head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_meta_content("og:site_name")

        # Assert
        assert result == "Example Site"

    def test_get_meta_content_nonexistent(self):
        """Test extracting content from non-existent meta tag returns None."""
        # Arrange
        html = """
        <html>
        <head></head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_meta_content("nonexistent")

        # Assert
        assert result is None

    def test_get_canonical_url(self):
        """Test extracting canonical URL."""
        # Arrange
        html = """
        <html>
        <head>
            <link rel="canonical" href="https://example.com/canonical-page">
        </head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_canonical_url()

        # Assert
        assert result == "https://example.com/canonical-page"

    def test_get_favicon(self):
        """Test extracting favicon."""
        # Arrange
        html = """
        <html>
        <head>
            <link rel="icon" href="/favicon.ico">
        </head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_favicon()

        # Assert
        assert result == "https://example.com/favicon.ico"

    def test_get_language(self):
        """Test extracting language from html tag."""
        # Arrange
        html = """
        <html lang="en">
        <head></head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_language()

        # Assert
        assert result == "en"

    def test_get_twitter_data(self):
        """Test extracting Twitter Card metadata."""
        # Arrange
        html = """
        <html>
        <head>
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:site" content="@example">
            <meta name="twitter:title" content="Twitter Title">
            <meta name="twitter:description" content="Twitter Description">
        </head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_twitter_data()

        # Assert
        assert result["twitter_card"] == "summary_large_image"
        assert result["twitter_site"] == "@example"
        assert result["twitter_title"] == "Twitter Title"
        assert result["twitter_description"] == "Twitter Description"
        # Other fields should be None
        assert result["twitter_creator"] is None

    def test_get_extended_og_data(self):
        """Test extracting extended Open Graph metadata."""
        # Arrange
        html = """
        <html>
        <head>
            <meta property="og:type" content="article">
            <meta property="og:site_name" content="Example Site">
            <meta property="article:author" content="John Doe">
            <meta property="article:published_time" content="2023-01-01T00:00:00Z">
        </head>
        <body></body>
        </html>
        """
        parser = HTMLParser(html, "https://example.com")

        # Act
        result = parser.get_extended_og_data()

        # Assert
        assert result["type"] == "article"
        assert result["site_name"] == "Example Site"
        assert result["author"] == "John Doe"
        assert result["published_time"] == "2023-01-01T00:00:00Z"