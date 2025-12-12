# -*- coding: utf-8 -*-
import time
import logging
import asyncio
import random
import json
import hashlib
import uuid
from typing import Optional, Dict, Any, List, AsyncGenerator, Tuple
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
import redis.asyncio as redis
from collections import deque

logger = logging.getLogger(__name__)

from .browser_pool import BrowserPool
from .redis_cache import RedisCache
from .rate_limiter import RateLimiter
from .fetcher import PageFetcher
from .extractor import DataExtractor
from .task_engine import TaskEngine
from .metrics import update_browser_memory
from .anomaly_detector import anomaly_detector


class AsyncFacebookScraperStreaming:
    def __init__(self,
                 headless: bool = True,
                 max_concurrent: int = 6,
                 cache_ttl: int = 600,  # Increased from 300 to 600 seconds
                 enable_images: bool = False,  # Set to False for better performance
                 mode: str = "simple",
                 redis_url: Optional[str] = None,
                 use_browser_pool: bool = True,
                 max_pages_per_context: int = 5,
                 max_contexts: int = 5,
                 context_reuse_limit: int = 250):  # Increased from 20 to 250
        self.mode = mode
        self.headless = headless
        self.max_concurrent = max_concurrent
        self.cache_ttl = cache_ttl
        self.enable_images = enable_images
        self.use_browser_pool = use_browser_pool

        # caches
        self.redis_cache = RedisCache(redis_url, cache_ttl) if redis_url else None

        # browser pool with improved architecture: 1 browser -> many contexts -> many pages
        self.browser_pool = BrowserPool(max_contexts=max_contexts, max_pages_per_context=max_pages_per_context, context_reuse_limit=context_reuse_limit,
                                        browser_args=self._get_optimized_browser_args(),
                                        headless=self.headless, enable_images=self.enable_images) if use_browser_pool else None

        # Create components for the new architecture
        self.fetcher = PageFetcher(self.browser_pool) if self.browser_pool else None
        self.extractor = DataExtractor(mode=mode)
        self.task_engine = TaskEngine(
            fetcher=self.fetcher,
            extractor=self.extractor,
            redis_cache=self.redis_cache,
            rate_limiter=RateLimiter(max_requests_per_minute=30, max_concurrent=max_concurrent),
            cache_ttl=cache_ttl
        ) if self.fetcher and self.extractor else None

        # stats - now delegate to task engine
        self.stats = {
            "total_requests": 0,
            "cached_requests": 0,
            "successful_scrapes": 0,
            "failed_scrapes": 0,
            "total_time": 0.0
        }

    async def __aenter__(self):
        if self.browser_pool:
            await self.browser_pool.initialize()
        if self.redis_cache:
            await self.redis_cache.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser_pool:
            await self.browser_pool.close()
        if self.redis_cache:
            await self.redis_cache.close()
        logger.info(f"Scraper stats: {self.stats}")

    def _get_optimized_browser_args(self) -> List[str]:
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--window-size=1280,720',
            '--disable-gpu',
            '--disable-software-rasterizer',
        ]
        if not self.enable_images:
            args.extend(['--blink-settings=imagesEnabled=false', '--disable-images'])
        return args

    async def get_facebook_metadata(self, url: str, mode: str = None) -> Dict[str, Any]:
        """Public method with layered cache and rate limiting - now uses new architecture"""
        if not self.task_engine:
            raise RuntimeError("Task engine not initialized")
            
        # Use provided mode or default to instance mode
        selected_mode = mode or self.mode
        result = await self.task_engine.get_facebook_metadata(url, mode=selected_mode)
        # Update stats from task engine
        self.stats = self.task_engine.get_engine_stats()
        return result

    async def get_multiple_metadata_streaming(self, urls: List[str], mode: str = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream results as they complete (deduped). Now uses task engine."""
        if not self.task_engine:
            raise RuntimeError("Task engine not initialized")
            
        # Use provided mode or default to instance mode
        selected_mode = mode or self.mode
        unique_urls = list(dict.fromkeys(urls))
        logger.info(f"Scraping {len(unique_urls)} unique URLs (from {len(urls)} input) in mode: {selected_mode}")

        async def _wrap(url):
            try:
                res = await self.task_engine.get_facebook_metadata(url, mode=selected_mode)
            except Exception as e:
                res = {"url": url, "error": str(e), "success": False}
            return url, res

        tasks = [asyncio.create_task(_wrap(u)) for u in unique_urls]

        # stream in completion order
        for coro in asyncio.as_completed(tasks):
            url, res = await coro
            yield {"url": url, "data": res}

    async def get_multiple_metadata(self, urls: List[str], mode: str = None, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """Get multiple metadata using the task engine"""
        if not self.task_engine:
            raise RuntimeError("Task engine not initialized")
            
        # Use provided mode or default to instance mode
        selected_mode = mode or self.mode
        if batch_size is None:
            batch_size = min(self.max_concurrent, max(1, len(urls)))
        results = {}
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} URLs) in mode: {selected_mode}")
            async for item in self.task_engine.get_multiple_metadata_streaming(batch, mode=selected_mode):
                results[item['url']] = item['data']
        return results