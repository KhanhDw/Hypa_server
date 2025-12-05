from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Setup logging configuration
from app.core.logging_config import setup_logging
setup_logging(log_level="INFO", log_file="app.log")

# Load application settings
from app.core.config import settings

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration using settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Import services after app initialization to avoid circular dependencies
from app.services.container import ServiceContainer

# Initialize services using container
service_container = ServiceContainer()
metadata_service = service_container.get_metadata_service()

from urllib.parse import urlparse

# -------------------------------------------------------
# Endpoint /metadata (Uses service layer)
# -------------------------------------------------------
@app.get("/metadata")
@limiter.limit(settings.rate_limit_default)  # Use configured rate limit
async def metadata(request: Request, url: str):
    # Additional validation for URL parameter
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="URL parameter is required")

    # Check if URL has valid format
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL format")

    return await metadata_service.get_metadata(url)


# -------------------------------------------------------
# Homepage
# -------------------------------------------------------
@app.get("/")
def home():
    return {"message": "Simple Server is running!"}