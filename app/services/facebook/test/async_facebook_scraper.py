# async_facebook_scraper.py
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class AsyncFacebookScraper:
    def __init__(self, headless=True):
        self.headless = headless
        self._cache = {}

    async def get_facebook_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        start = time.time()

        if url in self._cache and time.time() - self._cache[url]['timestamp'] < 300:
            return self._cache[url]['data']

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(java_script_enabled=True)
                page = await context.new_page()

                async def route_handler(route):
                    if route.request.resource_type in ["image", "media", "font"]:
                        await route.abort()
                    else:
                        await route.continue_()

                await page.route("**/*", route_handler)

                await page.goto(url, wait_until="domcontentloaded", timeout=15000)

                metadata = await page.evaluate("""() => {
                    const d = {
                        url: location.href,
                        title: document.title,
                        og_data: {},
                        basic_meta: {}
                    };

                    for (let m of document.querySelectorAll("meta")) {
                        const prop = m.getAttribute("property") || m.getAttribute("name");
                        const val = m.getAttribute("content");
                        if (!prop || !val) continue;

                        if (prop.startsWith("og:"))
                            d.og_data[prop.substring(3)] = val;
                        else if (["description","keywords"].includes(prop))
                            d.basic_meta[prop] = val;
                    }
                    return d;
                }""")

                metadata["scrape_time"] = time.time() - start
                metadata["timestamp"] = time.time()

                self._cache[url] = {"data": metadata, "timestamp": time.time()}

                await browser.close()
                return metadata

        except Exception as e:
            logger.error(f"Async error: {e}")
            return None

    async def get_multiple_metadata(self, urls: List[str]):
        tasks = [self.get_facebook_metadata(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for url, data in zip(urls, results):
            output[url] = None if isinstance(data, Exception) else data
        return output
