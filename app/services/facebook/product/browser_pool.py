# -*- coding: utf-8 -*-
import time
import logging
import asyncio
import random
from typing import List, Tuple, Optional, Dict
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)


class BrowserPool:
    """Quản lý pool browser/context/page để tái sử dụng.

    Thiết kế:
      - Tạo browser_args một lần, lưu trong self.browser_args (không dùng _impl internals)
      - Khi tạo page, đăng ký route handler 1 lần
      - Lưu map page -> context để khi trả page về pool có thể reset cookies/localStorage
    """

    def __init__(self, max_pages_per_browser: int = 6, browser_reuse_limit: int = 200, browser_args: List[str] = None,
                 headless: bool = True, enable_images: bool = True):
        self.max_pages_per_browser = max_pages_per_browser
        self.browser_reuse_limit = browser_reuse_limit
        self.browser_args = browser_args or [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--window-size=1280,720',
        ]
        self.headless = headless
        self.enable_images = enable_images

        self._playwright = None
        # list of tuples: (browser, use_count)
        self._browsers: List[Tuple[Browser, int]] = []
        # pages queue (Page objects ready to use)
        self._page_queue: asyncio.Queue = asyncio.Queue()
        # map page -> context (for resets)
        self._page_context_map: Dict[Page, BrowserContext] = {}
        self._lock = asyncio.Lock()

        # user agents
        self._user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]

    async def initialize(self):
        self._playwright = await async_playwright().start()
        browser = await self._playwright.chromium.launch(headless=self.headless, args=self.browser_args)
        self._browsers.append((browser, 0))
        await self._create_pages(browser, self.max_pages_per_browser)

    def _get_random_user_agent(self) -> str:
        return random.choice(self._user_agents)

    def _route_handler_factory(self, enable_images: bool):
        # create a closure route handler to register on page creation
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

    async def _create_pages(self, browser: Browser, count: int):
        for _ in range(count):
            context = await browser.new_context(
                java_script_enabled=True,
                viewport={'width': 1280, 'height': 720},
                user_agent=self._get_random_user_agent(),
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }
            )
            page = await context.new_page()
            page.set_default_navigation_timeout(15000)
            page.set_default_timeout(10000)
            # Register route handler ONCE per page
            await page.route("**/*", self._route_handler_factory(self.enable_images))
            # store mapping
            self._page_context_map[page] = context
            await self._page_queue.put(page)

    async def get_page(self) -> Page:
        """Lấy page từ pool, tạo thêm browser + pages nếu cần."""
        if self._page_queue.empty():
            async with self._lock:
                if self._page_queue.empty():
                    # try to reuse primary browser
                    browser, use_count = self._browsers[0]
                    if use_count < self.browser_reuse_limit:
                        await self._create_pages(browser, max(1, self.max_pages_per_browser // 2))
                        self._browsers[0] = (browser, use_count + max(1, self.max_pages_per_browser // 2))
                    else:
                        # create a new browser using stored args
                        new_browser = await self._playwright.chromium.launch(headless=self.headless, args=self.browser_args)
                        self._browsers.append((new_browser, 0))
                        await self._create_pages(new_browser, self.max_pages_per_browser)

        page: Page = await self._page_queue.get()
        return page

    async def return_page(self, page: Page):
        """Reset page state (cookies/localStorage/sessionStorage) and trả về pool"""
        try:
            context = self._page_context_map.get(page)
            if context:
                try:
                    await context.clear_cookies()
                except Exception:
                    pass
                try:
                    # clear storages in page
                    await page.evaluate("() => { try{ localStorage.clear(); sessionStorage.clear(); } catch(e){} }")
                except Exception:
                    pass
            # navigate to about:blank to reduce memory for that page
            try:
                await page.goto("about:blank", wait_until="domcontentloaded", timeout=3000)
            except Exception:
                pass
            # put back
            await self._page_queue.put(page)
        except Exception:
            # if anything fails, attempt to close page and remove it
            try:
                await page.close()
            except Exception:
                pass

    async def close(self):
        # close pages
        while not self._page_queue.empty():
            try:
                page = await self._page_queue.get()
                try:
                    ctx = self._page_context_map.pop(page, None)
                    await page.close()
                    if ctx:
                        await ctx.close()
                except Exception:
                    pass
            except Exception:
                pass

        # close browsers
        for browser, _ in self._browsers:
            try:
                await browser.close()
            except Exception:
                pass

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass