# -*- coding: utf-8 -*-
import time
import logging
import asyncio
import random
from typing import Optional, Dict, Any
from playwright.async_api import Page
import json

logger = logging.getLogger(__name__)

from .browser_pool import BrowserPool
from .metrics import observe_navigation_duration


class PageFetcher:
    """
    Fetcher layer: Handle page navigation and basic scraping
    """
    def __init__(self, browser_pool: BrowserPool):
        self.browser_pool = browser_pool

    async def fetch_page_content(self, page: Page, url: str, mode: str = "simple") -> Dict[str, Any]:
        """Navigate to URL and return the page for extraction"""
        start = time.time()
        try:
            # Try with DOM content loaded first
            await page.goto(url, wait_until="domcontentloaded", timeout=12000, referer="https://www.facebook.com/")
        except Exception as e:
            # Fallback to shorter wait
            logger.debug(f"First goto failed {url}: {e}")
            try:
                await page.goto(url, wait_until="commit", timeout=7000)
            except Exception as e2:
                raise e2

        # Wait a bit for dynamic content
        await page.wait_for_timeout(random.uniform(600, 1600))
        
        navigation_time = time.time() - start
        observe_navigation_duration(navigation_time, mode)
        
        # Return page object and timing info for extractor to use
        return {
            "page": page,
            "url": url,
            "navigation_time": navigation_time,
            "success": True,
            "timestamp": time.time()
        }