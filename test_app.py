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

if __name__ == "__main__":
    pytest.main([__file__])