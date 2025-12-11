import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urlparse
from typing import Dict, Optional, List, Any
import logging

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FacebookMetadataService:
    """Service để lấy metadata từ URL Facebook"""

    def __init__(self, use_selenium: bool = False, headless: bool = True):
        """
        Args:
            use_selenium: Có sử dụng Selenium không
            headless: Chạy Chrome ở chế độ headless
        """
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.use_selenium = use_selenium
        self.headless = headless
        self.driver = None

    def init_selenium_driver(self):
        """Khởi tạo Selenium WebDriver"""
        try:
            chrome_options = ChromeOptions()

            if self.headless:
                chrome_options.add_argument('--headless=new')  # New headless mode
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')

            # Thêm các options để tránh bị phát hiện là bot
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-popup-blocking')

            # Sử dụng webdriver-manager để tự động quản lý ChromeDriver
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # Thực thi script để ẩn webdriver
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            return True
        except Exception as e:
            logger.error(f"Không thể khởi tạo Selenium driver: {e}")
            return False

    def close_selenium_driver(self):
        """Đóng Selenium WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass

    def is_valid_facebook_url(self, url: str) -> bool:
        """Kiểm tra xem URL có phải là Facebook hợp lệ không"""
        try:
            parsed = urlparse(url)
            facebook_domains = [
                'facebook.com',
                'fb.watch',
                'fb.com',
                'fb.gg',
                'fb.me',
                'facebookcorewwwi.onion',  # Facebook onion site
            ]
            return any(domain in parsed.netloc for domain in facebook_domains)
        except:
            return False

    def extract_metadata(self, html_content: str) -> Dict:
        """
        Trích xuất Open Graph metadata từ HTML content

        Returns:
            Dict chứa các metadata
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        metadata = {
            'title': None,
            'description': None,
            'image': None,
            'images': [],
            'video': None,
            'videos': [],
            'video_type': None,
            'duration': None,
            'url': None,
            'type': None,
            'site_name': 'Facebook',
            'published_time': None,
            'author': None,
            'locale': None
        }

        # Tìm tất cả meta tags
        meta_tags = soup.find_all('meta')

        for tag in meta_tags:
            prop = tag.get('property', '')
            name = tag.get('name', '')
            content = tag.get('content', '')

            # Xử lý Open Graph tags
            if prop.startswith('og:'):
                prop_name = prop.replace('og:', '')

                if prop_name == 'title' and content:
                    metadata['title'] = content
                elif prop_name == 'description' and content:
                    metadata['description'] = content
                elif prop_name == 'image' and content:
                    metadata['image'] = content
                    if content not in metadata['images']:
                        metadata['images'].append(content)
                elif prop_name == 'video' and content:
                    metadata['video'] = content
                    if content not in metadata['videos']:
                        metadata['videos'].append(content)
                elif prop_name == 'video:url' and content:
                    if content not in metadata['videos']:
                        metadata['videos'].append(content)
                    if not metadata['video']:
                        metadata['video'] = content
                elif prop_name == 'video:type' and content:
                    metadata['video_type'] = content
                elif prop_name == 'video:duration' and content:
                    metadata['duration'] = content
                elif prop_name == 'url' and content:
                    metadata['url'] = content
                elif prop_name == 'type' and content:
                    metadata['type'] = content
                elif prop_name == 'site_name' and content:
                    metadata['site_name'] = content
                elif prop_name == 'published_time' and content:
                    metadata['published_time'] = content
                elif prop_name == 'author' and content:
                    metadata['author'] = content
                elif prop_name == 'locale' and content:
                    metadata['locale'] = content

            # Xử lý Twitter cards
            elif name.startswith('twitter:'):
                twitter_prop = name.replace('twitter:', '')
                if twitter_prop == 'title' and content and not metadata['title']:
                    metadata['title'] = content
                elif twitter_prop == 'description' and content and not metadata['description']:
                    metadata['description'] = content
                elif twitter_prop == 'image' and content and not metadata['image']:
                    metadata['image'] = content
                    if content not in metadata['images']:
                        metadata['images'].append(content)

            # Fallback: Kiểm tra các meta tags thông thường
            elif name == 'description' and content and not metadata['description']:
                metadata['description'] = content

        # Nếu không có OG title, sử dụng title tag
        if not metadata['title']:
            title_tag = soup.find('title')
            if title_tag and title_tag.text:
                metadata['title'] = title_tag.text.strip()

        # Tìm thêm video và ảnh từ các thẻ khác
        self._extract_additional_media(soup, metadata)

        return metadata

    def _extract_additional_media(self, soup: BeautifulSoup, metadata: Dict):
        """Trích xuất thêm media từ các thẻ HTML"""
        # Tìm video sources
        video_tags = soup.find_all(['video', 'source'])
        for tag in video_tags:
            src = tag.get('src') or tag.get('data-src')
            if src and src.startswith('http') and src not in metadata['videos']:
                metadata['videos'].append(src)

        # Tìm ảnh
        img_tags = soup.find_all('img', src=True)
        for img in img_tags[:20]:  # Giới hạn số lượng
            src = img.get('src') or img.get('data-src')
            if src and src.startswith('http') and src not in metadata['images']:
                metadata['images'].append(src)

    def get_with_requests(self, url: str, timeout: int = 15) -> Optional[str]:
        """Lấy HTML sử dụng requests (cho non-JS content)"""
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=timeout,
                allow_redirects=True
            )
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                return response.text
        except Exception as e:
            logger.warning(f"Requests failed: {e}")

        return None

    def get_with_selenium(self, url: str, timeout: int = 30) -> Optional[str]:
        """Lấy HTML sử dụng Selenium (cho JS-rendered content)"""
        if not self.driver:
            if not self.init_selenium_driver():
                return None

        try:
            logger.info(f"Đang truy cập với Selenium: {url}")
            self.driver.get(url)

            # Chờ trang load
            time.sleep(3)

            # Chờ các element meta xuất hiện
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "meta"))
                )
            except:
                logger.warning("Meta tags not found, but continuing...")

            # Cuộn trang để kích hoạt lazy loading
            self.driver.execute_script("window.scrollTo(0, 500)")
            time.sleep(2)

            # Thử tìm video player
            try:
                video_elements = self.driver.find_elements(By.TAG_NAME, "video")
                if video_elements:
                    logger.info(f"Tìm thấy {len(video_elements)} video elements")
            except:
                pass

            # Lấy HTML
            html_content = self.driver.page_source

            # Debug: Lưu HTML để kiểm tra
            # with open('debug_facebook.html', 'w', encoding='utf-8') as f:
            #     f.write(html_content)

            return html_content

        except Exception as e:
            logger.error(f"Selenium error: {e}")
            return None

    def get_facebook_metadata(self, url: str, timeout: int = 30) -> Dict:
        """
        Lấy metadata từ URL Facebook

        Returns:
            Dict chứa metadata và thông tin trạng thái
        """
        result = {
            'success': False,
            'error': None,
            'metadata': None,
            'url': url,
            'method': 'unknown'
        }

        try:
            # Kiểm tra URL
            if not self.is_valid_facebook_url(url):
                result['error'] = 'URL không phải là Facebook hợp lệ'
                return result

            html_content = None

            # Strategy 1: Thử với requests trước (nhanh hơn)
            if not self.use_selenium:
                logger.info(f"Thử với requests: {url}")
                html_content = self.get_with_requests(url, timeout=10)
                result['method'] = 'requests'

            # Strategy 2: Nếu requests thất bại hoặc yêu cầu Selenium, dùng Selenium
            if not html_content or self.use_selenium:
                logger.info(f"Thử với Selenium: {url}")
                html_content = self.get_with_selenium(url, timeout)
                result['method'] = 'selenium'

            if not html_content:
                result['error'] = 'Không thể lấy được nội dung trang'
                return result

            # Trích xuất metadata
            metadata = self.extract_metadata(html_content)

            # Làm sạch và validate URLs
            metadata['images'] = self._clean_urls(metadata['images'])
            metadata['videos'] = self._clean_urls(metadata['videos'])

            # Chọn ảnh đại diện nếu chưa có
            if not metadata['image'] and metadata['images']:
                # Ưu tiên ảnh lớn (có chứa từ khóa như 'scontent', 'fbcdn')
                for img in metadata['images']:
                    if any(keyword in img for keyword in ['scontent', 'fbcdn', 'cdn.fbsbx']):
                        metadata['image'] = img
                        break
                if not metadata['image']:
                    metadata['image'] = metadata['images'][0]

            # Chọn video đại diện nếu chưa có
            if not metadata['video'] and metadata['videos']:
                metadata['video'] = metadata['videos'][0]

            # Cleanup metadata values
            for key in ['title', 'description']:
                if metadata.get(key):
                    metadata[key] = metadata[key].strip()

            result['metadata'] = metadata
            result['success'] = True

            logger.info(f"Lấy metadata thành công với {result['method']}: {metadata.get('title', 'No title')[:50]}...")

        except Exception as e:
            result['error'] = f"Error: {str(e)}"
            logger.error(f"Error processing {url}: {e}")

        finally:
            # Không đóng driver ngay để tái sử dụng
            pass

        return result

    def _clean_urls(self, urls: List[str]) -> List[str]:
        """Làm sạch danh sách URLs"""
        cleaned = []
        seen = set()

        for url in urls:
            if not url or not isinstance(url, str):
                continue

            # Clean URL
            url = url.strip()
            if '?' in url:
                url = url.split('?')[0]

            # Loại bỏ URLs không hợp lệ
            if url.startswith('http') and url not in seen:
                seen.add(url)
                cleaned.append(url)

        return cleaned

    def cleanup(self):
        """Dọn dẹp tài nguyên"""
        self.close_selenium_driver()


# Sử dụng cải tiến
if __name__ == "__main__":
    # Khởi tạo service với Selenium (khuyến nghị)
    service = FacebookMetadataService(use_selenium=True, headless=True)

    test_urls = [
        "https://www.facebook.com/share/p/19FTEP281g/",
        "https://www.facebook.com/share/v/1HU8Kjpa9j/",
        "https://www.facebook.com/photo/?fbid=825022167072586&set=a.142113198696823",
    ]

    try:
        for url in test_urls:
            print(f"\n{'='*60}")
            print(f"Đang xử lý: {url}")
            print(f"{'='*60}")

            result = service.get_facebook_metadata(url, timeout=30)

            if result['success']:
                meta = result['metadata']
                print(f"✅ Thành công (Phương thức: {result['method']})")
                print(f"📌 Tiêu đề: {meta.get('title', 'Không có')}")
                print(f"📝 Mô tả: {meta.get('description', 'Không có')[:150]}...")
                print(f"🖼️ Ảnh chính: {meta.get('image', 'Không có')}")
                print(f"📊 Tổng ảnh: {len(meta.get('images', []))}")
                if meta.get('images'):
                    print(f"   - 5 ảnh đầu: {meta['images'][:5]}")
                print(f"🎬 Video chính: {meta.get('video', 'Không có')}")
                print(f"📈 Tổng video: {len(meta.get('videos', []))}")
                print(f"📌 Loại: {meta.get('type', 'Không có')}")
                print(f"⏱️ Thời gian: {meta.get('published_time', 'Không có')}")
            else:
                print(f"❌ Thất bại: {result.get('error', 'Unknown error')}")

            time.sleep(2)  # Delay giữa các request

    finally:
        service.cleanup()