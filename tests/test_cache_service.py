import pytest
from app.services.cache_service import MetadataCache
from app.core.models import Metadata


class TestMetadataCache:
    """Unit tests for MetadataCache"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.cache = MetadataCache(maxsize=2, ttl=1)  # Small cache with short TTL for testing

    def test_set_and_get_metadata(self):
        """Test setting and getting metadata from cache."""
        # Arrange
        test_url = "https://example.com"
        test_metadata = Metadata(title="Test", description="A test page", url=test_url)

        # Act
        self.cache.set(test_url, test_metadata)
        result = self.cache.get(test_url)

        # Assert
        assert result is not None
        assert result.title == "Test"
        assert result.description == "A test page"
        assert result.url == test_url

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist returns None."""
        # Act
        result = self.cache.get("nonexistent")

        # Assert
        assert result is None

    def test_cache_eviction_when_full(self):
        """Test that cache evicts oldest items when full."""
        # Arrange - Fill cache to capacity
        metadata1 = Metadata(title="First", url="https://example1.com")
        metadata2 = Metadata(title="Second", url="https://example2.com")
        metadata3 = Metadata(title="Third", url="https://example3.com")

        # Act
        self.cache.set("key1", metadata1)
        self.cache.set("key2", metadata2)
        # Now cache is full, adding third should evict oldest (key1)
        self.cache.set("key3", metadata3)

        # Assert
        # key1 should be evicted, key2 and key3 should remain
        assert self.cache.get("key1") is None
        assert self.cache.get("key2") is not None
        assert self.cache.get("key3") is not None

    def test_cache_ttl_expiration(self):
        """Test that cache entries expire after TTL."""
        import time

        # Arrange - Create cache with very short TTL
        short_ttl_cache = MetadataCache(maxsize=10, ttl=0.01)  # 0.01 seconds
        test_url = "https://example.com"
        test_metadata = Metadata(title="Test", description="A test page", url=test_url)

        # Act
        short_ttl_cache.set(test_url, test_metadata)
        # Wait for TTL to expire
        time.sleep(0.02)
        result = short_ttl_cache.get(test_url)

        # Assert
        # Entry should have expired and returned None
        assert result is None

    def test_cache_overwrite_existing_key(self):
        """Test that setting a key that already exists updates the value."""
        # Arrange
        test_url = "https://example.com"
        original_metadata = Metadata(title="Original", url=test_url)
        updated_metadata = Metadata(title="Updated", url=test_url)

        # Act
        self.cache.set(test_url, original_metadata)
        result1 = self.cache.get(test_url)
        self.cache.set(test_url, updated_metadata)
        result2 = self.cache.get(test_url)

        # Assert
        assert result1.title == "Original"
        assert result2.title == "Updated"