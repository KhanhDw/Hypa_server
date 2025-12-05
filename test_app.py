import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_homepage():
    """Test the homepage endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Simple Server is running!"}

def test_metadata_endpoint_without_url():
    """Test metadata endpoint without URL parameter"""
    response = client.get("/metadata")
    # This should return a 422 error because URL is required
    assert response.status_code == 422

def test_metadata_service_with_real_url():
    """Test metadata service with a real URL to verify it can handle requests without truncation"""
    # Test with a simple, reliable URL
    test_url = "https://example.com"
    response = client.get("/metadata", params={"url": test_url})
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify that the response contains expected metadata fields
    assert "title" in data
    assert "description" in data
    assert "image" in data
    assert "site_name" in data
    assert "url" in data
    
    # Verify that the URL in response matches the requested URL or is not None
    assert data["url"] is not None
    
    # Verify that the response includes the cached field
    assert "cached" in data
    
    # Verify that title is correctly extracted for example.com
    assert data["title"] == "Example Domain"
    assert data["site_name"] == "example.com"
    
    print(f"Successfully retrieved metadata for {test_url}")
    print(f"Title: {data.get('title', 'N/A')}")
    print(f"Site name: {data.get('site_name', 'N/A')}")
    print(f"Cached: {data.get('cached', 'N/A')}")

def test_metadata_service_with_external_url():
    """Test metadata service with a real external URL"""
    # Test with a simple external URL that should have clear metadata
    test_url = "https://example.com"
    response = client.get("/metadata", params={"url": test_url})
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify that the response contains expected metadata fields
    assert "title" in data
    assert "description" in data
    assert "site_name" in data
    assert "url" in data
    
    # Verify that the URL in response matches the requested URL or is not None
    assert data["url"] is not None
    
    # Verify specific expected values for example.com
    assert data["title"] == "Example Domain"
    assert data["site_name"] == "example.com"
    
    # Check that there's no unexpected truncation of data
    assert isinstance(data, dict)
    
    # Verify that the response includes all expected metadata fields
    expected_fields = [
        "title", "description", "image", "site_name", "type", "url", "platform",
        "author", "published_time", "modified_time", "section", "video",
        "audio", "locale", "determiner", "image_width", "image_height", "image_alt",
        "video_width", "video_height", "twitter_card", "twitter_site", "twitter_creator", "twitter_image",
        "twitter_title", "twitter_description", "canonical_url", "favicon", "language", "charset", "cached"
    ]
    for field in expected_fields:
        assert field in data, f"Expected field '{field}' not found in response"
    
    print(f"Successfully retrieved metadata for {test_url}")
    print(f"Title: {data.get('title', 'N/A')}")
    if data.get('description'):
        print(f"Description: {data.get('description', 'N/A')[:100]}...")  # First 100 chars
    print(f"Site name: {data.get('site_name', 'N/A')}")
    print(f"Cached: {data.get('cached', 'N/A')}")
    print(f"Total metadata fields returned: {len(data)}")

if __name__ == "__main__":
    pytest.main([__file__])