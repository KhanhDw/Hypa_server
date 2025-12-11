# -*- coding: utf-8 -*-
import time
import logging
import asyncio
import json

from .browser_pool import BrowserPool
from .redis_cache import RedisCache
from .rate_limiter import RateLimiter
from .scraper_core import AsyncFacebookScraperStreaming
from .scraper_api import FacebookScraperAPI

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Example run (for local testing)
if __name__ == "__main__":
    async def demo():
        urls = [
            "https://www.facebook.com/share/p/1HMEAngzqM/",
            "https://www.facebook.com/share/p/14PkMdwKj5P/",
        ]
        conf = {
            "headless": True,
            "max_concurrent": 3,
            "cache_ttl": 600,
            "enable_images": True,
            "mode": "super",  # simple|full|super
            "redis_url": None,
            "use_browser_pool": True
        }
        async with AsyncFacebookScraperStreaming(**conf) as s:
            async for item in s.get_multiple_metadata_streaming(urls):
                print(json.dumps(item, indent=2, ensure_ascii=False))

    asyncio.run(demo())
