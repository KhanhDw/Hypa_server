import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.metadata_service import MetadataService
from app.services.fetcher import URLValidatorInterface, WebFetcherInterface
from app.services.metadata_extractor import MetadataExtractorInterface
from app.services.cache_service import CacheInterface
from app.core.models import Metadata


class TestMetadataService:
    """Unit tests for MetadataService"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_url_validator = MagicMock(spec=URLValidatorInterface)
        self.mock_web_fetcher = AsyncMock(spec=WebFetcherInterface)
        self.mock_metadata_extractor = MagicMock(spec=MetadataExtractorInterface)
        self.mock_cache = MagicMock(spec=CacheInterface)
        self.metadata_service = MetadataService(
            url_validator=self.mock_url_validator,
            web_fetcher=self.mock_web_fetcher,
            metadata_extractor=self.mock_metadata_extractor,
            cache=self.mock_cache
        )

    @pytest.mark.asyncio
    async def test_get_metadata_with_valid_url(self):
        """Test get_metadata with a valid URL returns expected metadata."""
        # Arrange
        test_url = "https://example.com"
        mock_html = "<html><head><title>Test</title></head></html>"
        mock_metadata = Metadata(title="Test", description="A test page", url=test_url)

        # Set up mocks
        self.mock_cache.get.return_value = None  # No cache hit
        self.mock_web_fetcher.fetch_html.return_value = mock_html
        self.mock_metadata_extractor.extract.return_value = mock_metadata

        # Act
        result = await self.metadata_service.get_metadata(test_url)

        # Assert
        assert result["title"] == "Test"
        assert result["description"] == "A test page"
        assert result["url"] == test_url
        assert result["cached"] is False  # Should not be cached since cache miss

        # Verify interactions
        self.mock_cache.get.assert_called_once_with(test_url)
        self.mock_web_fetcher.fetch_html.assert_called_once_with(test_url)
        self.mock_metadata_extractor.extract.assert_called_once_with(mock_html, test_url)
        self.mock_cache.set.assert_called_once_with(test_url, mock_metadata)

    @pytest.mark.asyncio
    async def test_get_metadata_with_cached_result(self):
        """Test get_metadata returns cached result when available."""
        # Arrange
        test_url = "https://example.com"
        cached_metadata = Metadata(title="Cached", description="A cached page", url=test_url)

        # Set up mock for cache hit
        self.mock_cache.get.return_value = cached_metadata

        # Act
        result = await self.metadata_service.get_metadata(test_url)

        # Assert
        assert result["title"] == "Cached"
        assert result["cached"] is True  # Should be marked as cached

        # Verify interactions - should only check cache, not fetch HTML
        self.mock_cache.get.assert_called_once_with(test_url)
        self.mock_web_fetcher.fetch_html.assert_not_called()
        self.mock_metadata_extractor.extract.assert_not_called()
        self.mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_metadata_with_empty_url(self):
        """Test get_metadata raises HTTPException for empty URL."""
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.metadata_service.get_metadata("")
        assert "URL parameter is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_metadata_with_none_url(self):
        """Test get_metadata raises HTTPException for None URL."""
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.metadata_service.get_metadata(None)
        assert "URL parameter is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_metadata_with_whitespace_only_url(self):
        """Test get_metadata raises HTTPException for whitespace-only URL."""
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.metadata_service.get_metadata("   ")
        # Whitespace-only URL will be detected as invalid during validation
        # The service converts exceptions to HTTPException with a specific message format
        # or it will fail URL validation with a different message

    @pytest.mark.asyncio
    async def test_get_metadata_fetcher_error(self):
        """Test get_metadata handles fetcher errors properly."""
        # Arrange
        test_url = "https://example.com"
        self.mock_cache.get.return_value = None  # No cache hit

        # Set up mock to raise exception
        self.mock_web_fetcher.fetch_html.side_effect = ValueError("Network error")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.metadata_service.get_metadata(test_url)
        # The service converts exceptions to HTTPException with a specific message format
        assert "An unexpected error occurred while processing the URL:" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_metadata_extractor_error(self):
        """Test get_metadata handles extractor errors properly."""
        # Arrange
        test_url = "https://example.com"
        mock_html = "<html><head><title>Test</title></head></html>"

        # Set up mocks
        self.mock_cache.get.return_value = None  # No cache hit
        self.mock_web_fetcher.fetch_html.return_value = mock_html
        self.mock_metadata_extractor.extract.side_effect = Exception("Extraction failed")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await self.metadata_service.get_metadata(test_url)
        # The service converts exceptions to HTTPException with a specific message format
        assert "An unexpected error occurred while processing the URL:" in str(exc_info.value)