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

# Import the route handler factory from browser pool
from .browser_pool import BrowserPool


class AsyncFacebookScraperStreaming:
    def __init__(self,
                 headless: bool = True,
                 max_concurrent: int = 6,
                 cache_ttl: int = 300,
                 enable_images: bool = True,
                 mode: str = "simple",
                 redis_url: Optional[str] = None,
                 use_browser_pool: bool = True):
        self.mode = mode
        self.headless = headless
        self.max_concurrent = max_concurrent
        self.cache_ttl = cache_ttl
        self.enable_images = enable_images
        self.use_browser_pool = use_browser_pool

        # caches
        self.redis_cache = RedisCache(redis_url, cache_ttl) if redis_url else None
        self._local_cache: Dict[str, Dict] = {}
        self._local_cache_capacity = 2000

        # browser pool
        self.browser_pool = BrowserPool(max_pages_per_browser=4, browser_reuse_limit=200,
                                        browser_args=self._get_optimized_browser_args(),
                                        headless=self.headless, enable_images=self.enable_images) if use_browser_pool else None

        # rate limiter
        self.rate_limiter = RateLimiter(max_requests_per_minute=30, max_concurrent=max_concurrent)

        # stats
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

    async def _extract_simple(self, page: Page) -> Dict:
        return await page.evaluate("""() => {
            const get = s => document.querySelector(s)?.content || null;
            return {
                title: get('meta[property="og:title"]') || document.title || null,
                description: get('meta[property="og:description"]') || get('meta[name="description"]') || null,
                image: get('meta[property="og:image"]') || null,
                url: get('meta[property="og:url"]') || window.location.href
            };
        }""")

    async def _extract_full(self, page: Page) -> Dict:
        return await page.evaluate("""() => {
            const result = {
                title: document.title || null,
                og_data: {},
                twitter_data: {},
                meta_tags: {},
                images: [],
                videos: []
            };
            document.querySelectorAll('meta').forEach(m => {
                const prop = m.getAttribute('property') || m.getAttribute('name');
                const content = m.getAttribute('content');
                if (prop && content) {
                    result.meta_tags[prop] = content;
                    if (prop.startsWith('og:')) result.og_data[prop.substring(3)] = content;
                    else if (prop.startsWith('twitter:')) result.twitter_data[prop.substring(8)] = content;
                }
            });
            document.querySelectorAll('img[src]').forEach(img => {
                try {
                    if (img.src && img.src.startsWith('http')) result.images.push({src: img.src, alt: img.alt || ''});
                } catch(e){}
            });
            document.querySelectorAll('video[src]').forEach(v => {
                try { if (v.src) result.videos.push(v.src); } catch(e){}
            });
            return result;
        }""")

    async def _extract_super(self, page: Page) -> Dict:
        """Super mode: full + innerText snippet of main article/content + json-ld"""
        # get full metadata first
        full = await self._extract_full(page)

        # get article-like text + JSON-LD
        extra = await page.evaluate("""() => {
            const result = {article_text: null, json_ld: []};
            // attempt to find main article/body text
            const selectors = [
                'article',
                '[role="article"]',
                'div[data-testid="post_message"]',
                'div[data-ad-preview="message"]',
                'div[data-ft]',
                'main'
            ];
            for (const s of selectors) {
                const el = document.querySelector(s);
                if (el && el.innerText && el.innerText.trim().length > 20) {
                    result.article_text = el.innerText.trim().substring(0, 2000);
                    break;
                }
            }
            if (!result.article_text) {
                // fallback: first paragraph-like text
                const p = document.querySelector('p');
                if (p && p.innerText && p.innerText.trim().length > 20) result.article_text = p.innerText.trim().substring(0,2000);
            }
            // JSON-LD
            document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                try { result.json_ld.push(JSON.parse(s.textContent)); } catch(e){}
            });
            return result;
        }""")

        # merge
        full['article_text'] = extra.get('article_text')
        full['json_ld'] = extra.get('json_ld', [])
        return full

    async def _scrape_page(self, page: Page, url: str) -> Dict[str, Any]:
        """Navigate + extract on a prepared page (no heavy retries)."""
        start = time.time()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=12000, referer="https://www.facebook.com/")
        except Exception as e:
            # try fallback shorter wait
            logger.debug(f"First goto failed {url}: {e}")
            try:
                await page.goto(url, wait_until="commit", timeout=7000)
            except Exception as e2:
                raise e2

        # wait a bit for dynamic content
        await page.wait_for_timeout(random.uniform(600, 1600))

        if self.mode == "simple":
            meta = await self._extract_simple(page)
        elif self.mode == "full":
            meta = await self._extract_full(page)
        else:
            meta = await self._extract_super(page)

        if not isinstance(meta, dict):
            meta = {"title": None}

        meta.update({
            "url": url,
            "scrape_time": time.time() - start,
            "success": True,
            "timestamp": time.time()
        })
        return meta

    async def _scrape_with_pool(self, url: str) -> Dict[str, Any]:
        page = None
        try:
            page = await self.browser_pool.get_page()
            # page already has route handler registered at creation
            result = await self._scrape_page(page, url)
            return result
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {"url": url, "error": str(e), "scrape_time": time.time() - time.time(), "success": False}
        finally:
            if page and self.browser_pool:
                await self.browser_pool.return_page(page)

    async def _scrape_without_pool(self, url: str) -> Dict[str, Any]:
        """Fallback: create ephemeral browser/context/page - heavier but isolated"""
        start = time.time()
        try:
            p = await async_playwright().start()
            browser = await p.chromium.launch(headless=self.headless, args=self._get_optimized_browser_args())
            context = await browser.new_context(
                java_script_enabled=True,
                viewport={'width': 1280, 'height': 720},
                user_agent=random.choice([
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ])
            )
            page = await context.new_page()
            # lightweight route handler
            await page.route("**/*", self._route_handler_factory(self.enable_images))
            try:
                meta = await self._scrape_page(page, url)
            finally:
                try:
                    await page.close()
                except Exception:
                    pass
                try:
                    await context.close()
                except Exception:
                    pass
                try:
                    await browser.close()
                except Exception:
                    pass
                try:
                    await p.stop()
                except Exception:
                    pass
            return meta
        except Exception as e:
            logger.error(f"Error ephemeral scraping {url}: {e}")
            return {"url": url, "error": str(e), "success": False, "scrape_time": time.time() - start}

    def _route_handler_factory(self, enable_images: bool):
        # Use the route handler from browser pool if available
        if self.browser_pool:
            return self.browser_pool._route_handler_factory(enable_images)
        else:
            # Create a route handler directly if no browser pool is used
            async def route_handler(route):
                req = route.request
                req_type = req.resource_type
                url = req.url.lower()

                blocked_domains = [
                    "google-analytics", "doubleclick", "googlesyndication", "adsystem", "analytics",
                ]
                # allow fbcdn.net and connect.facebook.net - don't block them
                if any(domain in url for domain in blocked_domains):
                    await route.abort()
                    return

                # block large fonts/stylesheets/media that aren't necessary, but keep stylesheet for proper render
                if req_type in ["media"]:
                    await route.abort()
                    return

                if not enable_images and req_type == "image":
                    await route.abort()
                    return

                await route.continue_()
            return route_handler

    async def get_facebook_metadata(self, url: str) -> Dict[str, Any]:
        """Public method with layered cache and rate limiting"""
        self.stats["total_requests"] += 1

        cache_key = hashlib.md5(url.encode()).hexdigest()[:12]
        # local cache check
        local = self._local_cache.get(cache_key)
        if local and (time.time() - local['timestamp'] < self.cache_ttl):
            self.stats["cached_requests"] += 1
            out = dict(local['data'])
            out['from_cache'] = True
            return out

        # redis cache check
        if self.redis_cache:
            try:
                rdata = await self.redis_cache.get(url)
                if rdata:
                    self.stats["cached_requests"] += 1
                    # normalize
                    rdata['from_cache'] = True
                    # update local
                    self._local_cache[cache_key] = {'data': rdata, 'timestamp': time.time()}
                    return rdata
            except Exception:
                logger.debug("Redis cache get failed", exc_info=True)

        # rate limit
        await self.rate_limiter.acquire()
        try:
            start = time.time()
            if self.use_browser_pool and self.browser_pool:
                result = await self._scrape_with_pool(url)
            else:
                result = await self._scrape_without_pool(url)

            if result and result.get("success"):
                self.stats["successful_scrapes"] += 1
                result['from_cache'] = False
                # save to caches
                self._local_cache[cache_key] = {'data': result.copy(), 'timestamp': time.time()}
                if len(self._local_cache) > self._local_cache_capacity:
                    # simple LRU-like eviction: remove oldest by timestamp
                    oldest_keys = sorted(self._local_cache.items(), key=lambda kv: kv[1]['timestamp'])[:len(self._local_cache)//10 + 1]
                    for k, _ in oldest_keys:
                        self._local_cache.pop(k, None)
                if self.redis_cache:
                    try:
                        await self.redis_cache.set(url, result)
                    except Exception:
                        logger.debug("Redis set failed", exc_info=True)
            else:
                self.stats["failed_scrapes"] += 1

            self.stats["total_time"] += result.get("scrape_time", 0) if isinstance(result, dict) else 0
            return result
        except Exception as e:
            logger.error(f"get_facebook_metadata error for {url}: {e}")
            self.stats["failed_scrapes"] += 1
            return {"url": url, "error": str(e), "success": False, "scrape_time": 0}
        finally:
            self.rate_limiter.release()

    async def get_multiple_metadata_streaming(self, urls: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream results as they complete (deduped). Limits concurrency by semaphore in RateLimiter."""
        unique_urls = list(dict.fromkeys(urls))
        logger.info(f"Scraping {len(unique_urls)} unique URLs (from {len(urls)} input)")

        async def _wrap(url):
            try:
                res = await self.get_facebook_metadata(url)
            except Exception as e:
                res = {"url": url, "error": str(e), "success": False}
            return url, res

        tasks = [asyncio.create_task(_wrap(u)) for u in unique_urls]

        # stream in completion order
        for coro in asyncio.as_completed(tasks):
            url, res = await coro
            yield {"url": url, "data": res}

    async def get_multiple_metadata(self, urls: List[str], batch_size: Optional[int] = None) -> Dict[str, Any]:
        if batch_size is None:
            batch_size = min(self.max_concurrent, max(1, len(urls)))
        results = {}
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} URLs)")
            async for item in self.get_multiple_metadata_streaming(batch):
                results[item['url']] = item['data']
        return results