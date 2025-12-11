# async_facebook_scraper_streaming.py
# -*- coding: utf-8 -*-
import time
import logging
import asyncio
import random
import json
from typing import Optional, Dict, Any, List, AsyncGenerator
from playwright.async_api import async_playwright
import hashlib

logger = logging.getLogger(__name__)


class AsyncFacebookScraperStreaming:
    def __init__(self, headless=True, max_concurrent=10, cache_ttl=300, enable_images=True, mode="simple"):
        """
        Args:
            headless: Chế độ headless
            max_concurrent: Số lượng browser tối đa chạy đồng thời
            cache_ttl: Thời gian cache (giây)
            enable_images: Bật/tắt load ảnh (True nếu cần scrape ảnh)
        """
        self.mode = "simple"
        self.headless = headless
        self.max_concurrent = max_concurrent
        self.cache_ttl = cache_ttl
        self.enable_images = enable_images
        self._cache = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Rotating User Agents
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
        ]

        # Browser args tối ưu
        self.browser_args = self._get_optimized_browser_args()

        # Theo dõi lượt sử dụng user agents
        self.ua_usage = {ua: 0 for ua in self.user_agents}

    def _get_optimized_browser_args(self) -> List[str]:
        """Tạo browser args tối ưu dựa trên cấu hình"""
        base_args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--window-size=1280,720',
            '--enable-fast-unload',
            '--disable-features=TranslateUI',
            '--disable-features=ImprovedCookieControls',
        ]

        if not self.enable_images:
            base_args.extend([
                '--blink-settings=imagesEnabled=false',
                '--disable-images',
            ])

        return base_args

    async def __aenter__(self):
        """Context manager để tái sử dụng browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=self.browser_args
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Dọn dẹp khi thoát"""
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    def _get_cache_key(self, url: str) -> str:
        """Tạo cache key từ URL"""
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _get_random_user_agent(self) -> str:
        """Lấy user agent ngẫu nhiên"""
        min_usage = min(self.ua_usage.values())
        candidates = [ua for ua, count in self.ua_usage.items() if count == min_usage]
        selected = random.choice(candidates)
        self.ua_usage[selected] += 1
        return selected

    def _create_route_handler(self):
        """Tạo route handler dựa trên cấu hình ảnh"""
        if not self.enable_images:
            async def route_handler_no_images(route):
                req_type = route.request.resource_type
                if req_type in ["image", "media", "font", "stylesheet"]:
                    await route.abort()
                else:
                    await route.continue_()
            return route_handler_no_images
        else:
            async def route_handler_with_images(route):
                req = route.request
                req_type = req.resource_type
                url = req.url.lower()

                if any(tracker in url for tracker in [
                    "google-analytics", "facebook.net", "doubleclick",
                    "googlesyndication", "adsystem", "adservice", "analytics",
                    "track", "pixel", "beacon"
                ]):
                    await route.abort()
                elif req_type in ["font", "stylesheet", "manifest"]:
                    await route.abort()
                else:
                    await route.continue_()
            return route_handler_with_images

    async def extract_simple(self, page):
        return await page.evaluate("""() => {
            const get = s => document.querySelector(s)?.content || null;

            const title =
                get('meta[property="og:title"]') ||
                get('meta[name="twitter:title"]') ||
                document.title ||
                null;

            const description =
                get('meta[property="og:description"]') ||
                get('meta[name="twitter:description"]') ||
                get('meta[name="description"]') ||
                null;

            const images = [];
            const ogImg = get('meta[property="og:image"]') || get('meta[name="twitter:image"]');
            if (ogImg) images.push(ogImg);

            if (images.length === 0) {
                const img = document.querySelector("img");
                if (img?.src) images.push(img.src);
            }

            const videos = [];
            const ogVid = get('meta[property="og:video"]');
            if (ogVid) videos.push(ogVid);

            const vid = document.querySelector("video");
            if (vid?.src) videos.push(vid.src);

            return { title, description, images, image: images.length > 0 ? images[0] : null, videos, video: videos.length > 0 ? videos[0] : null };
        }""") # do không dùng enableImages ở ("""() => { nên là không dùng self.enable_images

    async def extract_full(self, page):
        return await page.evaluate("""() => {
            const out = {
                title: document.title || null,
                description: null,
                images: [],
                videos: [],
                meta: {},
                jsonld: []
            };

            // Lấy toàn bộ meta tags
            document.querySelectorAll("meta").forEach(m => {
                const name = m.getAttribute("property") || m.getAttribute("name");
                if (name) out.meta[name] = m.getAttribute("content");
            });

            out.description =
                out.meta["og:description"] ||
                out.meta["description"] ||
                null;

            // JSON-LD
            document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                try {
                    out.jsonld.push(JSON.parse(s.textContent));
                } catch {}
            });

            // Images
            const imgs = document.querySelectorAll("img[src]");
            imgs.forEach(i => out.images.push(i.src));

            const ogImg = out.meta["og:image"];
            if (ogImg && !out.images.includes(ogImg)) out.images.unshift(ogImg);

            // Videos
            const vids = document.querySelectorAll("video[src]");
            vids.forEach(v => out.videos.push(v.src));

            const ogVid = out.meta["og:video"];
            if (ogVid && !out.videos.includes(ogVid)) out.videos.unshift(ogVid);

            return out;
        }""") # do không dùng enableImages ở ("""() => { nên là không dùng self.enable_images

    async def extract_super_full(self, page):
        return await page.evaluate("""(enableImages) => {
            // Object chứa tất cả metadata
                const result = {
                    // REQUIRED FIELDS (tối thiểu)
                    title: document.title,
                    description: '',
                    image: '',

                    // FULL METADATA (tất cả những gì có thể lấy)
                    url: window.location.href,
                    og_data: {},
                    twitter_data: {},
                    basic_meta: {},
                    json_ld: [],
                    images: [],
                    videos: [],
                    meta_tags: {},
                    page_info: {},
                    scrape_time: Date.now()
                };

                // === 1. LẤY TẤT CẢ META TAGS ===
                const metaTags = document.querySelectorAll('meta');
                for (const tag of metaTags) {
                    const prop = tag.getAttribute('property') || tag.getAttribute('name');
                    const content = tag.getAttribute('content');

                    if (prop && content) {
                        // Lưu tất cả meta tags
                        result.meta_tags[prop] = content;

                        // Phân loại OG tags
                        if (prop.startsWith('og:')) {
                            const key = prop.substring(3);
                            result.og_data[key] = content;

                            // Set required fields từ OG
                            if (key === 'title' && !result.title) result.title = content;
                            if (key === 'description') result.description = content;
                            if (key === 'image') result.image = content;
                        }
                        // Twitter cards
                        else if (prop.startsWith('twitter:')) {
                            const key = prop.substring(8);
                            if (!result.twitter_data) result.twitter_data = {};
                            result.twitter_data[key] = content;
                        }
                        // Basic meta
                        else if (['description', 'keywords', 'author', 'robots'].includes(prop)) {
                            result.basic_meta[prop] = content;
                            if (prop === 'description' && !result.description) {
                                result.description = content;
                            }
                        }
                    }
                }

                // === 2. NẾU CHƯA CÓ DESCRIPTION, TÌM TRONG CONTENT ===
                if (!result.description) {
                    // Thử từ meta description
                    const metaDesc = document.querySelector('meta[name="description"]');
                    if (metaDesc) result.description = metaDesc.getAttribute('content');

                    // Thử từ OG description
                    if (!result.description && result.og_data.description) {
                        result.description = result.og_data.description;
                    }

                    // Thử lấy đoạn text đầu tiên
                    if (!result.description) {
                        const firstParagraph = document.querySelector('p');
                        if (firstParagraph && firstParagraph.textContent.trim().length > 10) {
                            result.description = firstParagraph.textContent.trim().substring(0, 200);
                        }
                    }
                }

                // === 3. NẾU CHƯA CÓ IMAGE, TÌM ẢNH ===
                if (!result.image || result.image === '') {
                    // Ưu tiên OG image
                    if (result.og_data.image) {
                        result.image = result.og_data.image;
                    }
                    // Thử Twitter image
                    else if (result.twitter_data && result.twitter_data.image) {
                        result.image = result.twitter_data.image;
                    }
                    // Tìm ảnh đầu tiên trong page
                    else if (enableImages) {
                        const firstImg = document.querySelector('img');
                        if (firstImg && firstImg.src) {
                            result.image = firstImg.src;
                        }
                    }
                }

                // === 4. LẤY TITLE (ưu tiên OG title, twitter title) ===
                if (result.og_data.title && result.og_data.title !== '') {
                    result.title = result.og_data.title;
                } else if (result.twitter_data && result.twitter_data.title) {
                    result.title = result.twitter_data.title;
                }

                // === 5. LẤY JSON-LD ===
                try {
                    const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
                    if (jsonLdScripts.length > 0) {
                        jsonLdScripts.forEach(script => {
                            try {
                                const jsonData = JSON.parse(script.textContent);
                                // Normalize JSON-LD
                                const normalized = {};

                                // Lấy tất cả field quan trọng
                                const importantFields = [
                                    '@type', '@context', 'name', 'headline', 'description',
                                    'image', 'url', 'author', 'datePublished', 'dateModified',
                                    'publisher', 'keywords', 'articleBody', 'thumbnailUrl'
                                ];

                                importantFields.forEach(field => {
                                    if (jsonData[field]) {
                                        if (field === 'image' && typeof jsonData[field] === 'object') {
                                            normalized[field] = jsonData[field].url || jsonData[field];
                                        } else {
                                            normalized[field] = jsonData[field];
                                        }
                                    }
                                });

                                if (Object.keys(normalized).length > 0) {
                                    result.json_ld.push(normalized);
                                }
                            } catch (e) {}
                        });
                    }
                } catch (e) {}

                // === 6. LẤY TẤT CẢ ẢNH (nếu enabled) ===
                if (enableImages) {
                    const imgElements = document.querySelectorAll('img');
                    imgElements.forEach(img => {
                        const src = img.src || img.getAttribute('data-src') ||
                                  img.getAttribute('data-lazy-src') || img.getAttribute('srcset');
                        if (src && (src.startsWith('http://') || src.startsWith('https://'))) {
                            result.images.push({
                                src: src,
                                alt: img.alt || '',
                                width: img.naturalWidth || img.width,
                                height: img.naturalHeight || img.height
                            });
                        }
                    });

                    // Sort images by size (largest first)
                    result.images.sort((a, b) => {
                        const sizeA = (a.width || 0) * (a.height || 0);
                        const sizeB = (b.width || 0) * (b.height || 0);
                        return sizeB - sizeA;
                    });
                }

                // === 7. LẤY VIDEO ===
                const videoElements = document.querySelectorAll('video, [data-video-url]');
                videoElements.forEach(video => {
                    const src = video.src || video.getAttribute('data-video-url') ||
                               video.getAttribute('poster');
                    if (src) {
                        result.videos.push({
                            src: src,
                            type: video.tagName.toLowerCase(),
                            poster: video.getAttribute('poster') || ''
                        });
                    }
                });

                // === 8. LẤY PAGE INFO ===
                result.page_info = {
                    url: window.location.href,
                    hostname: window.location.hostname,
                    protocol: window.location.protocol,
                    canonical: document.querySelector('link[rel="canonical"]')?.href || '',
                    charset: document.characterSet || document.charset || '',
                    language: document.documentElement.lang || '',
                    doctype: document.doctype ? document.doctype.name : ''
                };

                return result;
        }""", self.enable_images)


    async def _scrape_single(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape một URL (không có cache check) - Tối ưu cho Facebook"""
        start = time.time()
        user_agent = self._get_random_user_agent()

        try:
            context = await self.browser.new_context(
                java_script_enabled=True,
                viewport={'width': 1280, 'height': 720},
                user_agent=user_agent,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                }
            )

            page = await context.new_page()
            page.set_default_navigation_timeout(15000)
            page.set_default_timeout(10000)

            route_handler = self._create_route_handler()
            await page.route("**/*", route_handler)

            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Facebook cần JS để load content, dùng networkidle
            await page.goto(
                url,
                wait_until="networkidle",
                timeout=15000,
                referer="https://www.facebook.com/"
            )

            # Chờ thêm để Facebook content load
            await page.wait_for_timeout(random.uniform(2000, 4000))

            # Lấy TẤT CẢ metadata có thể
            # metadata = await page.evaluate("""(enableImages) => {
            #     // Object chứa tất cả metadata
            #     const result = {
            #         // REQUIRED FIELDS (tối thiểu)
            #         title: document.title,
            #         description: '',
            #         image: '',

            #         // FULL METADATA (tất cả những gì có thể lấy)
            #         url: window.location.href,
            #         og_data: {},
            #         twitter_data: {},
            #         basic_meta: {},
            #         json_ld: [],
            #         images: [],
            #         videos: [],
            #         meta_tags: {},
            #         page_info: {},
            #         scrape_time: Date.now()
            #     };

            #     // === 1. LẤY TẤT CẢ META TAGS ===
            #     const metaTags = document.querySelectorAll('meta');
            #     for (const tag of metaTags) {
            #         const prop = tag.getAttribute('property') || tag.getAttribute('name');
            #         const content = tag.getAttribute('content');

            #         if (prop && content) {
            #             // Lưu tất cả meta tags
            #             result.meta_tags[prop] = content;

            #             // Phân loại OG tags
            #             if (prop.startsWith('og:')) {
            #                 const key = prop.substring(3);
            #                 result.og_data[key] = content;

            #                 // Set required fields từ OG
            #                 if (key === 'title' && !result.title) result.title = content;
            #                 if (key === 'description') result.description = content;
            #                 if (key === 'image') result.image = content;
            #             }
            #             // Twitter cards
            #             else if (prop.startsWith('twitter:')) {
            #                 const key = prop.substring(8);
            #                 if (!result.twitter_data) result.twitter_data = {};
            #                 result.twitter_data[key] = content;
            #             }
            #             // Basic meta
            #             else if (['description', 'keywords', 'author', 'robots'].includes(prop)) {
            #                 result.basic_meta[prop] = content;
            #                 if (prop === 'description' && !result.description) {
            #                     result.description = content;
            #                 }
            #             }
            #         }
            #     }

            #     // === 2. NẾU CHƯA CÓ DESCRIPTION, TÌM TRONG CONTENT ===
            #     if (!result.description) {
            #         // Thử từ meta description
            #         const metaDesc = document.querySelector('meta[name="description"]');
            #         if (metaDesc) result.description = metaDesc.getAttribute('content');

            #         // Thử từ OG description
            #         if (!result.description && result.og_data.description) {
            #             result.description = result.og_data.description;
            #         }

            #         // Thử lấy đoạn text đầu tiên
            #         if (!result.description) {
            #             const firstParagraph = document.querySelector('p');
            #             if (firstParagraph && firstParagraph.textContent.trim().length > 10) {
            #                 result.description = firstParagraph.textContent.trim().substring(0, 200);
            #             }
            #         }
            #     }

            #     // === 3. NẾU CHƯA CÓ IMAGE, TÌM ẢNH ===
            #     if (!result.image || result.image === '') {
            #         // Ưu tiên OG image
            #         if (result.og_data.image) {
            #             result.image = result.og_data.image;
            #         }
            #         // Thử Twitter image
            #         else if (result.twitter_data && result.twitter_data.image) {
            #             result.image = result.twitter_data.image;
            #         }
            #         // Tìm ảnh đầu tiên trong page
            #         else if (enableImages) {
            #             const firstImg = document.querySelector('img');
            #             if (firstImg && firstImg.src) {
            #                 result.image = firstImg.src;
            #             }
            #         }
            #     }

            #     // === 4. LẤY TITLE (ưu tiên OG title, twitter title) ===
            #     if (result.og_data.title && result.og_data.title !== '') {
            #         result.title = result.og_data.title;
            #     } else if (result.twitter_data && result.twitter_data.title) {
            #         result.title = result.twitter_data.title;
            #     }

            #     // === 5. LẤY JSON-LD ===
            #     try {
            #         const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
            #         if (jsonLdScripts.length > 0) {
            #             jsonLdScripts.forEach(script => {
            #                 try {
            #                     const jsonData = JSON.parse(script.textContent);
            #                     // Normalize JSON-LD
            #                     const normalized = {};

            #                     // Lấy tất cả field quan trọng
            #                     const importantFields = [
            #                         '@type', '@context', 'name', 'headline', 'description',
            #                         'image', 'url', 'author', 'datePublished', 'dateModified',
            #                         'publisher', 'keywords', 'articleBody', 'thumbnailUrl'
            #                     ];

            #                     importantFields.forEach(field => {
            #                         if (jsonData[field]) {
            #                             if (field === 'image' && typeof jsonData[field] === 'object') {
            #                                 normalized[field] = jsonData[field].url || jsonData[field];
            #                             } else {
            #                                 normalized[field] = jsonData[field];
            #                             }
            #                         }
            #                     });

            #                     if (Object.keys(normalized).length > 0) {
            #                         result.json_ld.push(normalized);
            #                     }
            #                 } catch (e) {}
            #             });
            #         }
            #     } catch (e) {}

            #     // === 6. LẤY TẤT CẢ ẢNH (nếu enabled) ===
            #     if (enableImages) {
            #         const imgElements = document.querySelectorAll('img');
            #         imgElements.forEach(img => {
            #             const src = img.src || img.getAttribute('data-src') ||
            #                       img.getAttribute('data-lazy-src') || img.getAttribute('srcset');
            #             if (src && (src.startsWith('http://') || src.startsWith('https://'))) {
            #                 result.images.push({
            #                     src: src,
            #                     alt: img.alt || '',
            #                     width: img.naturalWidth || img.width,
            #                     height: img.naturalHeight || img.height
            #                 });
            #             }
            #         });

            #         // Sort images by size (largest first)
            #         result.images.sort((a, b) => {
            #             const sizeA = (a.width || 0) * (a.height || 0);
            #             const sizeB = (b.width || 0) * (b.height || 0);
            #             return sizeB - sizeA;
            #         });
            #     }

            #     // === 7. LẤY VIDEO ===
            #     const videoElements = document.querySelectorAll('video, [data-video-url]');
            #     videoElements.forEach(video => {
            #         const src = video.src || video.getAttribute('data-video-url') ||
            #                    video.getAttribute('poster');
            #         if (src) {
            #             result.videos.push({
            #                 src: src,
            #                 type: video.tagName.toLowerCase(),
            #                 poster: video.getAttribute('poster') || ''
            #             });
            #         }
            #     });

            #     // === 8. LẤY PAGE INFO ===
            #     result.page_info = {
            #         url: window.location.href,
            #         hostname: window.location.hostname,
            #         protocol: window.location.protocol,
            #         canonical: document.querySelector('link[rel="canonical"]')?.href || '',
            #         charset: document.characterSet || document.charset || '',
            #         language: document.documentElement.lang || '',
            #         doctype: document.doctype ? document.doctype.name : ''
            #     };

            #     return result;
            # }""", self.enable_images)

            if self.mode == "simple":
                metadata = await self.extract_simple(page)
            elif self.mode == "full":
                metadata = await self.extract_full(page)
            elif self.mode == "super":
                metadata = await self.extract_super_full(page)
            else:
                metadata = await self.extract_simple(page)



            metadata["scrape_time"] = time.time() - start
            metadata["success"] = True
            metadata["user_agent"] = user_agent
            metadata["timestamp"] = time.time()

            # Đóng page và context
            await page.close()
            await context.close()

            return metadata

        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)[:100]}")
            return {
                "url": url,
                "error": str(e),
                "scrape_time": time.time() - start,
                "success": False,
                "user_agent": user_agent
            }

    async def get_facebook_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Public method với cache"""
        cache_key = self._get_cache_key(url)

        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_ttl:
                cached_data = cached['data'].copy()
                cached_data['from_cache'] = True
                cached_data['cached_time'] = time.time() - cached['timestamp']
                return cached_data

        async with self._semaphore:
            try:
                result = await self._scrape_single(url)

                if result and result.get('success'):
                    result['from_cache'] = False
                    result['cache_key'] = cache_key

                    self._cache[cache_key] = {
                        'data': result.copy(),
                        'timestamp': time.time()
                    }

                    if len(self._cache) > 1000:
                        self._cleanup_old_cache()

                return result

            except Exception as e:
                logger.error(f"Error in get_facebook_metadata for {url}: {str(e)[:100]}")
                return {
                    "url": url,
                    "error": str(e),
                    "success": False,
                    "scrape_time": 0
                }

    async def get_multiple_metadata_streaming(self, urls: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream results - trả về ngay khi xong"""
        logger.info(f"Starting streaming scrape of {len(urls)} URLs")

        # Tạo tasks và stream results
        tasks = []
        for url in urls:
            task = asyncio.create_task(self.get_facebook_metadata(url))
            tasks.append((url, task))

        # Sử dụng as_completed để stream results
        for url, task in tasks:
            try:
                result = await task
                yield {"url": url, "data": result}
            except Exception as e:
                yield {"url": url, "data": {
                    "url": url,
                    "error": str(e),
                    "success": False
                }}

    async def get_multiple_metadata(self, urls: List[str], batch_size: int = None) -> Dict[str, Any]:
        """Batch processing với streaming results"""
        if batch_size is None:
            batch_size = self.max_concurrent

        results = {}
        total_urls = len(urls)

        logger.info(f"Starting batch scrape of {total_urls} URLs with batch size {batch_size}")

        for i in range(0, total_urls, batch_size):
            batch = urls[i:i + batch_size]
            batch_num = i // batch_size + 1

            logger.info(f"Processing batch {batch_num} ({len(batch)} URLs)")

            # Stream results trong batch
            async for result in self.get_multiple_metadata_streaming(batch):
                url = result["url"]
                data = result["data"]
                results[url] = data

                # Log ngay khi có result
                if data.get('success'):
                    logger.info(f"✓ {url} - {data.get('scrape_time', 0):.2f}s")
                else:
                    logger.error(f"✗ {url} - {data.get('error', 'Unknown error')}")

        logger.info(f"Completed scraping {total_urls} URLs")
        return results

    def _cleanup_old_cache(self):
        """Tự động dọn cache cũ"""
        now = time.time()
        old_keys = [
            key for key, value in self._cache.items()
            if now - value['timestamp'] > self.cache_ttl
        ]
        for key in old_keys:
            del self._cache[key]

        if old_keys:
            logger.info(f"Cleaned up {len(old_keys)} old cache entries")

    def format_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format metadata để hiển thị đẹp"""
        if not metadata or not metadata.get('success'):
            return "No metadata available"

        output = []
        output.append("=" * 80)
        output.append(f"URL: {metadata.get('url', 'N/A')}")
        output.append(f"Success: {metadata.get('success', False)}")
        output.append(f"Scrape Time: {metadata.get('scrape_time', 0):.2f}s")
        output.append(f"From Cache: {metadata.get('from_cache', False)}")
        output.append("-" * 80)

        # REQUIRED FIELDS
        output.append("📌 REQUIRED FIELDS:")
        output.append(f"  Title: {metadata.get('title', 'N/A')}")
        output.append(f"  Description: {metadata.get('description', 'N/A')[:100]}...")
        output.append(f"  Image: {metadata.get('image', 'N/A')}")

        # OG DATA
        if metadata.get('og_data'):
            output.append("\n🔍 OPEN GRAPH DATA:")
            for key, value in metadata['og_data'].items():
                if value and isinstance(value, str):
                    output.append(f"  og:{key}: {value[:80]}{'...' if len(value) > 80 else ''}")

        # TWITTER DATA
        if metadata.get('twitter_data'):
            output.append("\n🐦 TWITTER CARD DATA:")
            for key, value in metadata['twitter_data'].items():
                if value and isinstance(value, str):
                    output.append(f"  twitter:{key}: {value[:80]}{'...' if len(value) > 80 else ''}")

        # BASIC META
        if metadata.get('basic_meta'):
            output.append("\n📄 BASIC META:")
            for key, value in metadata['basic_meta'].items():
                if value:
                    output.append(f"  {key}: {value[:80]}{'...' if len(value) > 80 else ''}")

        # JSON-LD
        if metadata.get('json_ld') and len(metadata['json_ld']) > 0:
            output.append(f"\n📊 JSON-LD: {len(metadata['json_ld'])} objects found")
            for i, ld in enumerate(metadata['json_ld'][:2]):  # Show first 2
                output.append(f"  Object {i+1}: {ld.get('@type', 'Unknown')}")
                if ld.get('name'):
                    output.append(f"    Name: {ld['name'][:50]}...")
                if ld.get('image'):
                    output.append(f"    Image: {ld['image'][:80]}...")

        # IMAGES
        if metadata.get('images'):
            output.append(f"\n🖼️ IMAGES: {len(metadata['images'])} found")
            for i, img in enumerate(metadata['images'][:3]):  # Show first 3
                output.append(f"  Image {i+1}: {img['src'][:80]}...")
                if img.get('alt'):
                    output.append(f"    Alt: {img['alt'][:50]}...")

        # META TAGS COUNT
        if metadata.get('meta_tags'):
            output.append(f"\n🏷️ ALL META TAGS: {len(metadata['meta_tags'])} tags")
            # Show some important ones
            important_tags = ['viewport', 'theme-color', 'robots', 'generator']
            for tag in important_tags:
                if tag in metadata['meta_tags']:
                    output.append(f"  {tag}: {metadata['meta_tags'][tag]}")

        output.append("=" * 80)
        return "\n".join(output)


# Example usage với streaming
async def main():
    # Cấu hình logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    urls = [
        "https://www.facebook.com/share/p/1HMEAngzqM/",
        "https://www.facebook.com/share/p/14PkMdwKj5P/",
        "https://www.facebook.com/share/p/17gQ6Lg5Pf/",
        "https://www.facebook.com/share/p/16Zfzau1N1/",
        "https://www.facebook.com/share/p/1G45H7VBja/"
    ]

    print("🚀 STARTING STREAMING SCRAPING")
    print("=" * 80)

    async with AsyncFacebookScraperStreaming(
        headless=True,
        max_concurrent=5,
        cache_ttl=600,
        enable_images=True
    ) as scraper:

        # PHƯƠNG PHÁP 1: Streaming (trả về ngay khi xong)
        print("\n📡 METHOD 1: STREAMING RESULTS (as they complete)")
        print("-" * 80)

        start_time = time.time()
        all_results = []  # Lưu tất cả kết quả để in JSON cuối cùng

        async for result in scraper.get_multiple_metadata_streaming(urls):
            url = result["url"]
            data = result["data"]

            # Lưu kết quả
            all_results.append({
                "url": url,
                "data": data
            })

            print(f"\n➡️ Result for: {url}")
            print(f"   Status: {'✅ SUCCESS' if data.get('success') else '❌ FAILED'}")
            print(f"   Time: {data.get('scrape_time', 0):.2f}s")

            if data.get('success'):
                # Hiển thị metadata đầy đủ
                formatted = scraper.format_metadata(data)
                print(formatted)
            else:
                print(f"   Error: {data.get('error', 'Unknown')}")

        print(f"\n⏱️ Total streaming time: {time.time() - start_time:.2f}s")

        print("\n" + "=" * 80)
        print("📊 METHOD 2: BATCH PROCESSING WITH STREAMING")
        print("-" * 80)

        # PHƯƠNG PHÁP 2: Batch với streaming internal
        batch_results = await scraper.get_multiple_metadata(urls, batch_size=3)

        print(f"\n📋 FINAL RESULTS SUMMARY:")
        print("-" * 80)

        successful = sum(1 for data in batch_results.values() if data.get('success'))
        failed = len(batch_results) - successful

        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")

        # =============================================
        # HIỂN THỊ ĐẦY ĐỦ METADATA DẠNG JSON
        # =============================================
        print("\n" + "=" * 80)
        print("📄 FULL METADATA IN JSON FORMAT")
        print("=" * 80)

        # Tạo dictionary chứa tất cả metadata
        full_metadata = {
            "scrape_info": {
                "total_urls": len(urls),
                "successful": successful,
                "failed": failed,
                "scrape_timestamp": time.time(),
                "cache_enabled": True,
                "cache_ttl": scraper.cache_ttl
            },
            "results": {}
        }

        # Thêm metadata từng URL vào dictionary
        for url, data in batch_results.items():
            # Đảm bảo tất cả dữ liệu có thể serialize thành JSON
            serializable_data = {}
            for key, value in data.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    serializable_data[key] = value
                elif isinstance(value, dict):
                    # Xử lý nested dictionaries
                    serializable_data[key] = {}
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, (str, int, float, bool, type(None))):
                            serializable_data[key][sub_key] = sub_value
                        else:
                            serializable_data[key][sub_key] = str(sub_value)
                elif isinstance(value, list):
                    # Xử lý lists
                    serializable_data[key] = []
                    for item in value:
                        if isinstance(item, (str, int, float, bool, type(None))):
                            serializable_data[key].append(item)
                        elif isinstance(item, dict):
                            # Xử lý dict trong list
                            serializable_item = {}
                            for item_key, item_value in item.items():
                                if isinstance(item_value, (str, int, float, bool, type(None))):
                                    serializable_item[item_key] = item_value
                                else:
                                    serializable_item[item_key] = str(item_value)
                            serializable_data[key].append(serializable_item)
                        else:
                            serializable_data[key].append(str(item))
                else:
                    # Chuyển đổi các kiểu dữ liệu khác thành string
                    serializable_data[key] = str(value)

            full_metadata["results"][url] = serializable_data

        # In JSON ra terminal với format đẹp
        print("\nFULL JSON OUTPUT:")
        print("=" * 80)
        json_output = json.dumps(full_metadata, indent=2, ensure_ascii=False)
        print(json_output)

        # Lưu JSON vào file (tùy chọn)
        timestamp = int(time.time())
        filename = f"facebook_metadata_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(full_metadata, f, indent=2, ensure_ascii=False)
        print(f"\n✅ JSON đã được lưu vào file: {filename}")

        # =============================================
        # HIỂN THỊ TÓM TẮT METADATA THEO TỪNG URL
        # =============================================
        print("\n" + "=" * 80)
        print("📊 METADATA SUMMARY BY URL")
        print("=" * 80)

        for url, data in batch_results.items():
            if data.get('success'):
                print(f"\n🔗 URL: {url}")
                print(f"   Title: {data.get('title', 'N/A')}")
                print(f"   Description: {data.get('description', 'N/A')[:100]}...")
                print(f"   Main Image: {data.get('image', 'N/A')}")

                # Thống kê metadata
                stats = []
                if data.get('og_data'):
                    stats.append(f"OG tags: {len(data['og_data'])}")
                if data.get('twitter_data'):
                    stats.append(f"Twitter tags: {len(data['twitter_data'])}")
                if data.get('meta_tags'):
                    stats.append(f"Total meta tags: {len(data['meta_tags'])}")
                if data.get('images'):
                    stats.append(f"Images: {len(data['images'])}")
                if data.get('json_ld'):
                    stats.append(f"JSON-LD objects: {len(data['json_ld'])}")

                if stats:
                    print(f"   Metadata: {', '.join(stats)}")

                # Hiển thị các meta tags quan trọng
                print("\n   Important Meta Tags:")
                important_meta = [
                    ('og:title', 'Title'),
                    ('og:description', 'Description'),
                    ('og:image', 'Image'),
                    ('og:url', 'URL'),
                    ('og:type', 'Type'),
                    ('twitter:title', 'Twitter Title'),
                    ('twitter:description', 'Twitter Description'),
                    ('twitter:image', 'Twitter Image'),
                    ('description', 'Meta Description'),
                    ('keywords', 'Keywords')
                ]

                for meta_key, display_name in important_meta:
                    if data.get('meta_tags') and meta_key in data['meta_tags']:
                        value = data['meta_tags'][meta_key]
                        truncated = value[:80] + "..." if len(value) > 80 else value
                        print(f"     {display_name}: {truncated}")


if __name__ == "__main__":
    asyncio.run(main())