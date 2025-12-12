# -*- coding: utf-8 -*-
import time
import logging
import asyncio
import random
from typing import List, Tuple, Optional, Dict, Set
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger(__name__)

from .metrics import update_active_contexts, update_active_pages, update_browser_memory


class BrowserPool:
    """Quản lý pool browser/context/page để tái sử dụng hiệu quả hơn.

    Cải tiến:
      - 1 browser -> nhiều context -> mỗi context nhiều page (tối ưu RAM)
      - Không reset page sau mỗi lần sử dụng, chỉ reset context sau N lần sử dụng
      - Giảm thời gian chờ bằng cách không xóa cookies/storage mỗi lần
      - Thêm metrics để theo dõi tài nguyên
    """

    def __init__(self, max_contexts: int = 8, max_pages_per_context: int = 8, context_reuse_limit: int = 250, browser_args: List[str] = None,
                 headless: bool = True, enable_images: bool = True):
        self.max_contexts = max_contexts
        self.max_pages_per_context = max_pages_per_context
        self.context_reuse_limit = context_reuse_limit
        self.browser_args = browser_args or [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--window-size=1280,720',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-ipc-flooding-protection',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
            '--disable-restore-session-state',
            '--disable-new-avatar-menu',
            '--no-first-run',
            '--disable-default-apps',
            '--disable-extensions',
            '--disable-plugins',
            '--disable-translate',
            '--disable-ipc-flooding-protection',
            '--disable-background-networking',
            '--disable-sync',
            '--disable-databases',
            '--disable-webgl',
            '--disable-javascript-harmony-shipping',
            '--no-pings',
            '--no-zygote',
            '--disable-dev-shm-usage',
            '--disable-features=TranslateUI',
            '--disable-logging',
            '--disable-permissions-api',
            '--no-default-browser-check',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-ipc-flooding-protection',
            '--disable-background-timer-throttling',
            '--disable-renderer-accessibility',
            '--blink-settings=imagesEnabled=false',  # Disable images completely
            '--disable-images',  # Another flag to disable images
            '--disable-javascript',  # Disable JavaScript if not needed for metadata
            '--disable-plugins-discovery',  # Disable plugin discovery
            '--disable-audio-output',  # Disable audio output
        ]
        self.headless = headless
        self.enable_images = enable_images

        self._playwright = None
        self._browser = None  # Single browser for efficiency
        # contexts queue (list of tuples: (context, use_count))
        self._context_queue: asyncio.Queue = asyncio.Queue()
        # pages queue for each context (map context -> list of pages)
        self._context_pages_map: Dict[BrowserContext, List[Page]] = {}
        self._context_lock = asyncio.Lock()

        # Track active resources
        self._active_contexts = 0
        self._active_pages = 0

        # user agents
        self._user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]

    async def initialize(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless, args=self.browser_args)
        # Create initial contexts and pages
        for _ in range(self.max_contexts):
            context = await self._create_context()
            await self._create_pages(context, self.max_pages_per_context)
            await self._context_queue.put((context, 0))
            self._active_contexts += 1
            update_active_contexts(self._active_contexts)

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

    async def _create_context(self) -> BrowserContext:
        """Create a new context with random user agent"""
        context = await self._browser.new_context(
            java_script_enabled=True,
            viewport={'width': 1280, 'height': 720},
            user_agent=self._get_random_user_agent(),
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
        )
        self._active_contexts += 1
        update_active_contexts(self._active_contexts)
        return context

    async def _create_pages(self, context: BrowserContext, count: int):
        """Create pages for a context and add to the map"""
        if context not in self._context_pages_map:
            self._context_pages_map[context] = []
        
        for _ in range(count):
            page = await context.new_page()
            page.set_default_navigation_timeout(15000)
            page.set_default_timeout(10000)
            # Register route handler ONCE per page
            await page.route("**/*", self._route_handler_factory(self.enable_images))
            self._context_pages_map[context].append(page)
            self._active_pages += 1
            update_active_pages(self._active_pages)

    async def get_page(self) -> Tuple[Page, BrowserContext]:
        """Lấy page từ pool, tạo thêm context + pages nếu cần."""
        if self._context_queue.empty():
            async with self._context_lock:
                if self._context_queue.empty():
                    # Create a new context if we haven't reached the limit
                    context = await self._create_context()
                    await self._create_pages(context, self.max_pages_per_context)
                    await self._context_queue.put((context, 0))

        # Get a context from the queue
        context, use_count = await self._context_queue.get()
        use_count += 1

        # Check if we need to reset the context after N uses
        if use_count >= self.context_reuse_limit:
            # Close the current context and create a new one
            await context.close()
            self._active_contexts -= 1
            update_active_contexts(self._active_contexts)
            context = await self._create_context()
            await self._create_pages(context, self.max_pages_per_context)
            use_count = 1

        # Return a page from the context's available pages
        pages = self._context_pages_map.get(context, [])
        if not pages:
            await self._create_pages(context, 1)  # Create one more page if needed
            pages = self._context_pages_map[context]
            
        page = pages.pop()  # Get a page from the context
        self._active_pages -= 1  # Page is now in use, not in pool
        update_active_pages(self._active_pages)
        
        # Put the context back in the queue with updated use count
        await self._context_queue.put((context, use_count))
        
        return page, context

    async def return_page(self, page: Page, context: BrowserContext):
        """Return page to context pool for reuse (no reset for performance)"""
        try:
            # Navigate to about:blank to reduce memory but don't reset cookies/storage
            try:
                await page.goto("about:blank", wait_until="domcontentloaded", timeout=3000)
            except Exception:
                pass  # If navigation to blank fails, page might be broken but we still add it back
            
            # Add the page back to the context's pages list
            if context in self._context_pages_map:
                self._context_pages_map[context].append(page)
            else:
                # Context might have been recreated, create the mapping
                self._context_pages_map[context] = [page]
            self._active_pages += 1  # Page is back in pool
            update_active_pages(self._active_pages)
        except Exception as e:
            # If anything fails, attempt to close page to prevent leaks
            try:
                await page.close()
            except Exception:
                pass

    async def close(self):
        # Close all contexts
        while not self._context_queue.empty():
            try:
                context, _ = await self._context_queue.get()
                await context.close()
                self._active_contexts -= 1
                update_active_contexts(self._active_contexts)
            except Exception:
                pass

        # Close browser
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
