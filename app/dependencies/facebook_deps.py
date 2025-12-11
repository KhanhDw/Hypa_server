from app.services.facebook.facebook_scraper import AsyncFacebookScraperStreaming

scraper_service = AsyncFacebookScraperStreaming(
    headless=True,
    max_concurrent=5,
    cache_ttl=600,
    enable_images=True
)

async def get_scraper_service():
    """Dependency cho FastAPI"""
    async with scraper_service as service:
        yield service
