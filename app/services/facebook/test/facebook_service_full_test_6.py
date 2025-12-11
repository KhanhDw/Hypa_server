from playwright.sync_api import sync_playwright, TimeoutError
import json
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List
import logging
from functools import lru_cache

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FastFacebookScraper:
    def __init__(self, headless: bool = True, max_workers: int = 3):
        self.headless = headless
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # Cache cho các URL đã scrape
        self._cache = {}

    def get_facebook_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Lấy metadata từ Facebook với tốc độ tối ưu - FIXED VERSION
        """
        start_time = time.time()

        # Kiểm tra cache trước
        if url in self._cache:
            if time.time() - self._cache[url]['timestamp'] < 300:  # Cache 5 phút
                logger.info(f"Lấy từ cache: {url}")
                return self._cache[url]['data']

        try:
            with sync_playwright() as p:
                # Tối ưu hóa launch options cho tốc độ
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--window-size=1920,1080',
                        '--disable-extensions',
                        '--disable-gpu',
                        '--disable-software-rasterizer',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding',
                        '--disable-client-side-phishing-detection',
                        '--disable-component-update',
                        '--disable-domain-reliability',
                        '--disable-sync',
                        '--disable-translate',
                        '--metrics-recording-only',
                        '--no-first-run',
                        '--no-default-browser-check',
                        '--disable-default-apps',
                        '--mute-audio',
                        '--hide-scrollbars',
                        '--disable-notifications',
                        '--disable-logging',
                        '--disable-hang-monitor',
                        '--disable-prompt-on-repost',
                        '--disable-component-extensions-with-background-pages',
                        '--disable-breakpad',
                        '--disable-crash-reporter',
                        '--disable-device-discovery-notifications',
                        '--noerrdialogs',
                        '--disable-component-cloud-policy',
                        # Thêm flags để chặn resource
                        '--blink-settings=imagesEnabled=false',
                        '--disable-javascript-harmony-shipping',
                    ]
                )

                # Tạo context với tối ưu hóa
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='vi-VN',
                    timezone_id='Asia/Ho_Chi_Minh',
                    geolocation={'latitude': 10.8231, 'longitude': 106.6297},
                    permissions=['geolocation'],
                    color_scheme='light',
                    # Tắt các tính năng không cần thiết để tăng tốc
                    java_script_enabled=True,
                    bypass_csp=False,  # Đặt về False để tránh lỗi
                    ignore_https_errors=False,
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Cache-Control': 'max-age=0',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                    }
                )

                page = context.new_page()

                # FIX: Route handler đơn giản không dùng async
                def route_handler(route):
                    """Route handler đơn giản để chặn các resource không cần thiết"""
                    resource_type = route.request.resource_type
                    # Chỉ cho phép tải document, stylesheet, script
                    if resource_type in ['image', 'media', 'font', 'other', 'websocket']:
                        route.abort()
                    else:
                        route.continue_()

                # Đăng ký route handler
                page.route("**/*", route_handler)

                try:
                    # Điều hướng với timeout ngắn hơn và chế độ tối ưu
                    logger.info(f"Đang truy cập: {url}")

                    # Sử dụng networkidle với timeout ngắn hơn
                    page.goto(
                        url,
                        wait_until="domcontentloaded",  # Chỉ đợi DOM
                        timeout=20000,  # Giảm timeout xuống 20s
                        referer='https://www.facebook.com/'
                    )

                    # CHỈ chờ các element cần thiết cho metadata
                    try:
                        # Chờ title xuất hiện
                        page.wait_for_load_state('domcontentloaded', timeout=5000)
                    except TimeoutError:
                        # Nếu timeout, vẫn tiếp tục
                        pass

                    # Sử dụng JavaScript để lấy metadata nhanh hơn
                    metadata = page.evaluate("""() => {
                        const result = {
                            url: window.location.href,
                            title: document.title,
                            description: null,
                            image: null,
                            type: null,
                            site_name: null,
                            og_data: {},
                            basic_meta: {},
                            json_ld: []
                        };

                        // Lấy tất cả meta tags một lần - tối ưu hóa
                        const metaTags = document.getElementsByTagName('meta');
                        for (let i = 0; i < metaTags.length; i++) {
                            const tag = metaTags[i];
                            const property = tag.getAttribute('property') || tag.getAttribute('name');
                            const content = tag.getAttribute('content');

                            if (!property || !content) continue;

                            if (property.startsWith('og:')) {
                                const key = property.substring(3); // Bỏ 'og:'
                                result.og_data[key] = content;

                                // Gán vào các trường chính
                                if (key === 'title') result.title = content;
                                else if (key === 'description') result.description = content;
                                else if (key === 'image') result.image = content;
                                else if (key === 'type') result.type = content;
                                else if (key === 'site_name') result.site_name = content;
                            } else if (property === 'description' || property === 'keywords' || property === 'author') {
                                result.basic_meta[property] = content;
                            }
                        }

                        // Lấy JSON-LD nếu có
                        const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
                        for (let i = 0; i < jsonLdScripts.length; i++) {
                            try {
                                result.json_ld.push(JSON.parse(jsonLdScripts[i].textContent));
                            } catch(e) {
                                // Bỏ qua lỗi parse
                            }
                        }

                        return result;
                    }""")

                    # Thêm timestamp và thời gian xử lý
                    metadata['scrape_time'] = time.time() - start_time
                    metadata['timestamp'] = time.time()

                    # Lưu vào cache
                    self._cache[url] = {
                        'data': metadata,
                        'timestamp': time.time()
                    }

                    logger.info(f"Lấy metadata thành công trong {metadata['scrape_time']:.2f}s")
                    return metadata

                except TimeoutError:
                    logger.error(f"Timeout khi tải trang: {url}")
                    return None

                except Exception as e:
                    logger.error(f"Lỗi khi lấy dữ liệu: {e}")

                    # Thử fallback: lấy ít metadata hơn
                    try:
                        metadata = {
                            'url': url,
                            'title': page.title(),
                            'scrape_time': time.time() - start_time,
                            'timestamp': time.time(),
                            'error': str(e)
                        }
                        return metadata
                    except:
                        return None

                finally:
                    # Đóng browser nhanh
                    browser.close()

        except Exception as e:
            logger.error(f"Lỗi khởi tạo browser: {e}")
            return None

    def get_facebook_metadata_simple(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Phiên bản đơn giản hơn, không dùng route handler
        """
        start_time = time.time()

        # Kiểm tra cache
        if url in self._cache:
            if time.time() - self._cache[url]['timestamp'] < 300:
                logger.info(f"Lấy từ cache (simple): {url}")
                return self._cache[url]['data']

        try:
            with sync_playwright() as p:
                # Cấu hình tối giản để tăng tốc
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-images',  # Tắt hình ảnh
                        '--disable-plugins',  # Tắt plugins
                        '--blink-settings=imagesEnabled=false',
                        f'--window-size={1920},{1080}',
                    ]
                )

                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    java_script_enabled=True,
                )

                page = context.new_page()

                try:
                    logger.info(f"Đang truy cập (simple): {url}")

                    # Chỉ load DOM, không load resource
                    page.goto(
                        url,
                        wait_until="commit",  # Chỉ đợi commit - nhanh nhất
                        timeout=15000
                    )

                    # Đợi DOM tải xong
                    page.wait_for_load_state('domcontentloaded', timeout=5000)

                    # Lấy metadata nhanh
                    metadata = {
                        'url': url,
                        'title': page.title(),
                        'og_data': {},
                        'basic_meta': {},
                        'scrape_time': time.time() - start_time,
                        'timestamp': time.time()
                    }

                    # Lấy meta tags
                    meta_elements = page.query_selector_all('meta')
                    for meta in meta_elements:
                        try:
                            prop = meta.get_attribute('property') or meta.get_attribute('name')
                            content = meta.get_attribute('content')

                            if prop and content:
                                if prop.startswith('og:'):
                                    key = prop[3:]  # Bỏ 'og:'
                                    metadata['og_data'][key] = content
                                elif prop in ['description', 'keywords']:
                                    metadata['basic_meta'][prop] = content
                        except:
                            continue

                    # Cache
                    self._cache[url] = {
                        'data': metadata,
                        'timestamp': time.time()
                    }

                    logger.info(f"Lấy metadata (simple) trong {metadata['scrape_time']:.2f}s")
                    return metadata

                except Exception as e:
                    logger.error(f"Lỗi simple: {e}")
                    return None

                finally:
                    browser.close()

        except Exception as e:
            logger.error(f"Lỗi khởi tạo browser (simple): {e}")
            return None

    def get_multiple_metadata(self, urls: List[str], simple: bool = False) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Lấy metadata từ nhiều URL song song
        """
        results = {}

        # Chọn method
        method = self.get_facebook_metadata_simple if simple else self.get_facebook_metadata

        # Sử dụng ThreadPool để xử lý song song
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {executor.submit(method, url): url for url in urls}

            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    results[url] = future.result(timeout=30)
                except Exception as e:
                    logger.error(f"Lỗi khi xử lý {url}: {e}")
                    results[url] = None

        return results

    def clear_cache(self):
        """Xóa cache"""
        self._cache.clear()
        logger.info("Đã xóa cache")

# Phiên bản async đơn giản và hiệu quả
import asyncio
from playwright.async_api import async_playwright

class AsyncFacebookScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._cache = {}

    async def get_facebook_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Phiên bản async - FIXED và tối ưu
        """
        start_time = time.time()

        # Cache check
        if url in self._cache:
            if time.time() - self._cache[url]['timestamp'] < 300:
                logger.info(f"Lấy từ cache (async): {url}")
                return self._cache[url]['data']

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-images',
                        f'--window-size={1920},{1080}',
                    ]
                )

                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='vi-VN',
                )

                page = await context.new_page()

                # Async route handler đúng cách
                async def route_handler(route):
                    resource_type = route.request.resource_type
                    if resource_type in ['image', 'media', 'font', 'other']:
                        await route.abort()
                    else:
                        await route.continue_()

                await page.route("**/*", route_handler)

                try:
                    logger.info(f"Đang truy cập (async): {url}")

                    await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=15000
                    )

                    # Lấy metadata bằng JavaScript
                    metadata = await page.evaluate("""() => {
                        const data = {
                            url: window.location.href,
                            title: document.title,
                            og_data: {},
                            basic_meta: {},
                            json_ld: []
                        };

                        // Fast metadata extraction
                        const metas = document.querySelectorAll('meta');
                        metas.forEach(meta => {
                            const prop = meta.getAttribute('property') || meta.getAttribute('name');
                            const content = meta.getAttribute('content');

                            if (prop && content) {
                                if (prop.startsWith('og:')) {
                                    data.og_data[prop.substring(3)] = content;
                                } else if (prop === 'description' || prop === 'keywords') {
                                    data.basic_meta[prop] = content;
                                }
                            }
                        });

                        return data;
                    }""")

                    metadata['scrape_time'] = time.time() - start_time
                    metadata['timestamp'] = time.time()

                    # Cache
                    self._cache[url] = {
                        'data': metadata,
                        'timestamp': time.time()
                    }

                    logger.info(f"Lấy metadata async trong {metadata['scrape_time']:.2f}s")
                    return metadata

                except Exception as e:
                    logger.error(f"Lỗi async: {e}")
                    return None

                finally:
                    await browser.close()

        except Exception as e:
            logger.error(f"Lỗi khởi tạo browser async: {e}")
            return None

    async def get_multiple_metadata(self, urls: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Lấy nhiều metadata song song
        """
        tasks = [self.get_facebook_metadata(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.error(f"Lỗi với {url}: {result}")
                output[url] = None
            else:
                output[url] = result

        return output

# Hàm wrapper đơn giản
def get_facebook_metadata_fast(url: str, method: str = "simple") -> Optional[Dict[str, Any]]:
    """
    Hàm wrapper để lấy metadata nhanh
    method: "simple", "advanced", "async"
    """
    if method == "async":
        scraper = AsyncFacebookScraper(headless=True)
        return asyncio.run(scraper.get_facebook_metadata(url))
    elif method == "simple":
        scraper = FastFacebookScraper(headless=True)
        return scraper.get_facebook_metadata_simple(url)
    else:
        scraper = FastFacebookScraper(headless=True)
        return scraper.get_facebook_metadata(url)

# Hàm test nhanh
def quick_test():
    """Test nhanh các phương pháp"""
    import concurrent.futures

    test_url = "https://www.facebook.com/share/p/19FTEP281g/"

    print("=" * 60)
    print("QUICK TEST FACEBOOK SCRAPER")
    print("=" * 60)

    # Test các phương pháp
    methods = [
        ("Simple", "simple"),
        ("Advanced", "advanced"),
        ("Async", "async")
    ]

    for name, method in methods:
        print(f"\n{name} Method:")
        print("-" * 30)

        start = time.time()
        metadata = get_facebook_metadata_fast(test_url, method=method)
        elapsed = time.time() - start

        if metadata:
            print(f"  Time: {elapsed:.2f}s")
            print(f"  Title: {metadata.get('title', 'N/A')[:60]}...")
            print(f"  OG Title: {metadata.get('og_data', {}).get('title', 'N/A')[:60]}...")
        else:
            print(f"  Failed after {elapsed:.2f}s")

# Phiên bản siêu nhanh - chỉ lấy title và OG data cơ bản
def get_facebook_metadata_ultrafast(url: str) -> Optional[Dict[str, Any]]:
    """
    Phiên bản siêu nhanh - chỉ lấy dữ liệu tối thiểu
    """
    start_time = time.time()

    try:
        with sync_playwright() as p:
            # Browser cực tối giản
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-images',
                    '--disable-javascript',  # Tắt JS để nhanh hơn
                    '--disable-plugins',
                    '--disable-popup-blocking',
                    '--window-size=1,1',  # Window nhỏ nhất
                ]
            )

            context = browser.new_context(
                viewport={'width': 1, 'height': 1},  # Viewport nhỏ
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                java_script_enabled=False,  # Tắt JS
            )

            page = context.new_page()

            try:
                # Go với timeout rất ngắn
                response = page.goto(url, wait_until="commit", timeout=10000)

                if not response:
                    return None

                # Đọc HTML trực tiếp từ response nếu có thể
                html_content = page.content()

                # Parse đơn giản để lấy metadata
                metadata = {
                    'url': url,
                    'title': page.title()[:200],
                    'scrape_time': time.time() - start_time,
                }

                # Tìm OG tags đơn giản
                import re

                # Tìm og:title
                og_title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html_content)
                if og_title_match:
                    metadata['og_title'] = og_title_match.group(1)[:200]

                # Tìm og:description
                og_desc_match = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html_content)
                if og_desc_match:
                    metadata['og_description'] = og_desc_match.group(1)[:300]

                # Tìm og:image
                og_image_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html_content)
                if og_image_match:
                    metadata['og_image'] = og_image_match.group(1)

                return metadata

            except Exception as e:
                logger.error(f"Lỗi ultrafast: {e}")
                return None

            finally:
                browser.close()

    except Exception as e:
        logger.error(f"Lỗi browser ultrafast: {e}")
        return None

# Sử dụng
if __name__ == "__main__":
    import concurrent.futures

    url = "https://www.facebook.com/share/p/19FTEP281g/"

    print("=" * 60)
    print("FIXED FACEBOOK SCRAPER - MULTI-METHOD TEST")
    print("=" * 60)

    # Test ultrafast method
    print("\n1. UltraFast Method (No JS, minimal):")
    start = time.time()
    metadata_uf = get_facebook_metadata_ultrafast(url)
    elapsed = time.time() - start
    if metadata_uf:
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Title: {metadata_uf.get('title', 'N/A')}")
        if 'og_title' in metadata_uf:
            print(f"  OG Title: {metadata_uf.get('og_title', 'N/A')}")
    else:
        print(f"  Failed after {elapsed:.2f}s")

    # Test simple method
    print("\n2. Simple Method:")
    scraper = FastFacebookScraper(headless=True)
    start = time.time()
    metadata_simple = scraper.get_facebook_metadata_simple(url)
    elapsed = time.time() - start
    if metadata_simple:
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Title: {metadata_simple.get('title', 'N/A')}")
        print(f"  OG Data: {metadata_simple.get('og_data', {})}")
    else:
        print(f"  Failed after {elapsed:.2f}s")

    # Test advanced method
    print("\n3. Advanced Method:")
    start = time.time()
    scraperAs = AsyncFacebookScraper(headless=True)
    metadata_adv = scraperAs.get_facebook_metadata(url)
    elapsed = time.time() - start
    if metadata_adv:
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Title: {metadata_adv.get('title', 'N/A')}")
        # print(f"  OG Data: {len(metadata_adv.get('og_data', {}))} items")
        print(f"  OG Data: {metadata_adv.get('og_data', {})} ")
        if 'json_ld' in metadata_adv:
            print(f"  JSON-LD: {len(metadata_adv['json_ld'])} items")
    else:
        print(f"  Failed after {elapsed:.2f}s")

    # Test cache
    print("\n4. Cache Test (same URL again):")
    start = time.time()
    metadata_cached = scraper.get_facebook_metadata_simple(url)
    elapsed = time.time() - start
    print(f"  Time (cached): {elapsed:.2f}s")

    # Test batch
    print("\n5. Batch Test (2 URLs):")
    urls = [
        "https://www.facebook.com/share/p/19FTEP281g/",
        "https://www.facebook.com/facebook"
    ]

    start = time.time()
    results = scraper.get_multiple_metadata(urls, simple=True)
    elapsed = time.time() - start

    for url_result, metadata in results.items():
        if metadata:
            print(f"  {url_result[:50]}...: {metadata.get('scrape_time', 0):.2f}s")
        else:
            print(f"  {url_result[:50]}...: Failed")

    print(f"\nTotal batch time: {elapsed:.2f}s")

    # Quick test all methods
    print("\n" + "=" * 60)
    quick_test()

    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)

'''
# Lấy nhanh nhất có thể
from facebook_scraper import get_facebook_metadata_ultrafast

metadata = get_facebook_metadata_ultrafast(url)
if metadata and 'og_title' in metadata:
    # Đã có đủ dữ liệu cơ bản
    pass
else:
    # Fallback đến method chi tiết hơn
    from facebook_scraper import FastFacebookScraper
    scraper = FastFacebookScraper()
    metadata = scraper.get_facebook_metadata_simple(url)
'''