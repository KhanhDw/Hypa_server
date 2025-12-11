import pytest
import requests
import asyncio
from typing import Dict, Any

# Based on the router structure:
# main.py: app.include_router(router, prefix="/api/v1")
# app/routers/router.py: includes metadata routes with prefix="/metadata"
# app/routers/platforms/__init__.py: includes facebook router with prefix="/facebook"
# app/routers/platforms/facebook/router.py: includes facebook_router_full with prefix="/full"
# app/routers/platforms/facebook/facebook_router_full.py: has no additional prefix
# So the final path would be: /api/v1/metadata/facebook/full/metadata
# As specified by the user: http://127.0.0.1:8000/api/v1/metadata/facebook/full/metadata
BASE_URL = "http://127.0.0.1:8000/api/v1/metadata"

def test_facebook_metadata_endpoint():
    """
    Test the Facebook metadata endpoint with a sample URL
    """
    # Sample Facebook URL for testing
    test_url = "https://www.facebook.com/share/p/1Akpqhq1p6/"
    endpoint = f"{BASE_URL}/facebook/full/metadata"
    
    params = {
        "url": test_url
    }
    
    try:
        response = requests.get(endpoint, params=params)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        # Check if the request was successful
        assert response.status_code == 200
        
        # Parse the response JSON
        data = response.json()
        
        # Check if the response has the expected structure
        assert "success" in data
        assert data["success"] is True
        
        if data["success"]:
            assert "data" in data
            assert "url" in data["data"]
            print(f"Retrieved metadata for URL: {data['data']['url']}")
        else:
            print(f"Error: {data.get('error', 'Unknown error')}")
            
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Make sure the FastAPI server is running on http://127.0.0.1:8000")
        assert False, "Server connection failed"
    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
        assert False, f"Request failed: {str(e)}"
    except AssertionError:
        # Re-raise assertion errors
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        assert False, f"Unexpected error: {str(e)}"


def test_facebook_metadata_with_invalid_url():
    """
    Test the Facebook metadata endpoint with an invalid URL
    """
    # Invalid URL for testing error handling
    test_url = "https://invalid-url.com"
    endpoint = f"{BASE_URL}/facebook/full/metadata"
    
    params = {
        "url": test_url
    }
    
    try:
        response = requests.get(endpoint, params=params)
        
        print(f"Status Code for invalid URL: {response.status_code}")
        print(f"Response: {response.text}")
        
        # For an invalid URL, we expect a 400 (Bad Request) or 500 (Internal Server Error)
        assert response.status_code in [400, 500]
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Make sure the FastAPI server is running on http://127.0.0.1:8000")
        assert False, "Server connection failed"
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        assert False, f"Unexpected error: {str(e)}"


def test_facebook_health_check():
    """
    Test the Facebook health check endpoint
    """
    endpoint = f"{BASE_URL}/facebook/full/health"
    
    try:
        response = requests.get(endpoint)
        
        print(f"Health Check Status Code: {response.status_code}")
        print(f"Health Check Response: {response.text}")
        
        # Check if the request was successful
        assert response.status_code == 200
        
        # Parse the response JSON
        data = response.json()
        
        # Check if the response has the expected structure
        assert "status" in data
        assert data["status"] == "healthy"
        
        print(f"Service status: {data['status']}")
            
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Make sure the FastAPI server is running on http://127.0.0.1:8000")
        assert False, "Server connection failed"
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        assert False, f"Unexpected error: {str(e)}"


if __name__ == "__main__":
    print("Testing Facebook metadata endpoint...")
    test_facebook_metadata_endpoint()
    
    print("\nTesting Facebook metadata endpoint with invalid URL...")
    test_facebook_metadata_with_invalid_url()
    
    print("\nTesting Facebook health check endpoint...")
    test_facebook_health_check()
    
    print("\nAll tests completed!")

