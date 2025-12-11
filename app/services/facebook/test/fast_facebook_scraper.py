# fast_facebook_scraper.py
from playwright.sync_api import sync_playwright, TimeoutError
import json
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List
import logging
import concurrent.futures

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FastFacebookScraper:
    def __init__(self, headless: bool = True, max_workers: int = 3):
        self.headless = headless
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cache = {}

    def get_facebook_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Bản advanced"""
        start_time = time.time()

        if url in self._cache and time.time() - self._cache[url]['timestamp'] < 300:
            return self._cache[url]['data']

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                        '--window-size=1920,1080',
                        '--disable-extensions',
                        '--disable-gpu',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--blink-settings=imagesEnabled=false'
                    ]
                )

                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0',
                    java_script_enabled=True
                )

                page = context.new_page()

                def route_handler(route):
                    if route.request.resource_type in ['image', 'media', 'font', 'other', 'websocket']:
                        route.abort()
                    else:
                        route.continue_()

                page.route("**/*", route_handler)

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)

                    metadata = page.evaluate("""() => {
                        const result = {
                            url: location.href,
                            title: document.title,
                            og_data: {},
                            basic_meta: {},
                            json_ld: []
                        };

                        const metaTags = document.getElementsByTagName('meta');
                        for (let tag of metaTags) {
                            const prop = tag.getAttribute('property') || tag.getAttribute('name');
                            const content = tag.getAttribute('content');
                            if (!prop || !content) continue;

                            if (prop.startsWith('og:')) {
                                result.og_data[prop.substring(3)] = content;
                            } else if (['description', 'keywords', 'author'].includes(prop)) {
                                result.basic_meta[prop] = content;
                            }
                        }

                        return result;
                    }""")

                    metadata['scrape_time'] = time.time() - start_time
                    metadata['timestamp'] = time.time()

                    self._cache[url] = {'data': metadata, 'timestamp': time.time()}
                    return metadata

                finally:
                    browser.close()

        except Exception as e:
            logger.error(f"Lỗi khi scrape: {e}")
            return None

    def get_facebook_metadata_simple(self, url: str) -> Optional[Dict[str, Any]]:
        """Bản simple"""
        start = time.time()

        if url in self._cache and time.time() - self._cache[url]['timestamp'] < 300:
            return self._cache[url]['data']

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-images',
                        '--disable-plugins',
                        '--blink-settings=imagesEnabled=false'
                    ]
                )

                context = browser.new_context(java_script_enabled=True)
                page = context.new_page()
                page.goto(url, wait_until="commit", timeout=15000)

                metadata = {
                    'url': url,
                    'title': page.title(),
                    'og_data': {},
                    'basic_meta': {},
                    'scrape_time': time.time() - start
                }

                self._cache[url] = {'data': metadata, 'timestamp': time.time()}
                return metadata

        except Exception as e:
            logger.error(f"Lỗi simple: {e}")
            return None

    def clear_cache(self):
        self._cache.clear()


def get_facebook_metadata_ultrafast(url: str) -> Optional[Dict[str, Any]]:
    """Phiên bản siêu tối giản"""
    start = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(java_script_enabled=False)
            page = context.new_page()
            response = page.goto(url, wait_until="commit", timeout=10000)
            if not response:
                return None

            html = page.content()
            import re

            metadata = {
                "url": url,
                "title": page.title(),
                "scrape_time": time.time() - start
            }

            og_title = re.search(r'property="og:title"\s+content="([^"]+)"', html)
            if og_title:
                metadata["og_title"] = og_title.group(1)

            browser.close()
            return metadata

    except Exception as e:
        logger.error(e)
        return None


def get_facebook_metadata_fast(url: str, method="simple"):
    """Wrapper"""
    from async_facebook_scraper import AsyncFacebookScraper

    if method == "async":
        return asyncio.run(AsyncFacebookScraper().get_facebook_metadata(url))

    scraper = FastFacebookScraper()
    return scraper.get_facebook_metadata_simple(url) if method == "simple" \
        else scraper.get_facebook_metadata(url)
