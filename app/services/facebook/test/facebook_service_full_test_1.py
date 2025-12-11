import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urlparse, unquote
from typing import Dict, Optional, List, Any
import logging
import time

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FacebookContentExtractor:
    """Service để lấy FULL nội dung từ URL Facebook (không chỉ metadata)"""

    def __init__(self, use_selenium: bool = True, headless: bool = True):
        """
        Args:
            use_selenium: Luôn dùng Selenium để lấy full content
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
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def init_selenium_driver(self):
        """Khởi tạo Selenium WebDriver với cấu hình tối ưu cho Facebook"""
        try:
            chrome_options = ChromeOptions()

            if self.headless:
                chrome_options.add_argument('--headless=new')

            # Cấu hình để tránh bị phát hiện là bot
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # User agent và các headers
            chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-infobars')

            # Tắt các tính năng không cần thiết
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')

            # Tải ảnh (có thể tắt để tăng tốc)
            prefs = {
                'profile.default_content_setting_values': {
                    'images': 2,  # 1=Allow, 2=Block
                    'javascript': 1,
                    'plugins': 2,
                    'popups': 2,
                    'geolocation': 2,
                    'notifications': 2,
                    'auto_select_certificate': 2,
                    'fullscreen': 2,
                    'mouselock': 2,
                    'mixed_script': 2,
                    'media_stream': 2,
                    'media_stream_mic': 2,
                    'media_stream_camera': 2,
                    'protocol_handlers': 2,
                    'ppapi_broker': 2,
                    'automatic_downloads': 2,
                    'midi_sysex': 2,
                    'push_messaging': 2,
                    'ssl_cert_decisions': 2,
                    'metro_switch_to_desktop': 2,
                    'protected_media_identifier': 2,
                    'app_banner': 2,
                    'site_engagement': 2,
                    'durable_storage': 2
                }
            }
            chrome_options.add_experimental_option('prefs', prefs)

            # Tự động quản lý ChromeDriver
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # Ẩn automation
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en', 'vi']
                    });
                '''
            })

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

    def extract_full_content_selenium(self, url: str, timeout: int = 40) -> Dict:
        """
        Lấy FULL nội dung từ Facebook bằng Selenium

        Returns:
            Dict chứa full content và metadata
        """
        if not self.driver:
            if not self.init_selenium_driver():
                return {}

        result = {
            'full_title': '',
            'full_description': '',
            'full_text': '',
            'post_content': '',
            'author_name': '',
            'author_url': '',
            'post_time': '',
            'reactions_count': '',
            'comments_count': '',
            'shares_count': '',
            'hashtags': [],
            'mentions': [],
            'links': []
        }

        try:
            logger.info(f"Đang truy cập với Selenium: {url}")
            self.driver.get(url)

            # Chờ trang load
            time.sleep(5)

            # Cố gắng đăng nhập nếu cần (để xem nội dung private)
            # self._try_login_if_needed()

            # Cuộn trang để load nội dung
            self._scroll_page()

            # Đợi nội dung xuất hiện
            time.sleep(3)

            # Phân tích loại post
            post_type = self._detect_post_type()

            # Lấy full content dựa trên loại post
            if post_type == 'video':
                content = self._extract_video_content()
            elif post_type == 'photo':
                content = self._extract_photo_content()
            elif post_type == 'text':
                content = self._extract_text_content()
            elif post_type == 'share':
                content = self._extract_share_content()
            else:
                content = self._extract_general_content()

            # Gộp kết quả
            result.update(content)

            # Lấy thêm metadata từ HTML
            html_content = self.driver.page_source
            metadata = self._extract_metadata_from_html(html_content)

            # Kết hợp metadata
            result.update(metadata)

            # Làm sạch nội dung
            result = self._clean_content(result)

        except Exception as e:
            logger.error(f"Lỗi khi extract content: {e}")

        return result

    def _scroll_page(self):
        """Cuộn trang để load nội dung"""
        try:
            # Cuộn từ từ
            for i in range(3):
                scroll_amount = 500 * (i + 1)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_amount})")
                time.sleep(1)

            # Cuộn lên đầu trang
            self.driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(1)
        except:
            pass

    def _detect_post_type(self) -> str:
        """Phát hiện loại post Facebook"""
        try:
            page_source = self.driver.page_source.lower()

            # Kiểm tra các selector đặc trưng
            if 'video' in page_source and any(x in page_source for x in ['videoplayer', 'video player', 'fbwatch']):
                return 'video'
            elif 'photo' in page_source and any(x in page_source for x in ['photo-container', 'photo_', '/photo/']):
                return 'photo'
            elif 'shared a post' in page_source or 'shared a memory' in page_source:
                return 'share'
            elif 'status' in page_source or 'post' in page_source:
                return 'text'
            else:
                return 'general'
        except:
            return 'general'

    def _extract_video_content(self) -> Dict:
        """Trích xuất nội dung video post"""
        content = {}

        try:
            # Thử tìm tiêu đề video
            selectors = [
                'div[data-testid="story_header"] h2',
                'div[role="article"] h2',
                'div[data-ad-preview="message"]',
                'div[class*="userContent"]',
                'div[data-testid="post_message"]',
                'div[class*="postContent"]'
            ]

            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text:
                        content['full_title'] = element.text.strip()
                        break
                except:
                    continue

            # Thử tìm mô tả video
            desc_selectors = [
                'div[class*="videoDescription"]',
                'div[data-testid="videoDescription"]',
                'div[class*="captionText"]',
                'div[class*="descriptionText"]'
            ]

            for selector in desc_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text and not content.get('full_description'):
                        content['full_description'] = element.text.strip()
                except:
                    continue

            # Nếu không tìm thấy mô tả riêng, sử dụng tiêu đề
            if not content.get('full_description') and content.get('full_title'):
                content['full_description'] = content['full_title']

            # Lấy tên tác giả
            author_selectors = [
                'a[role="link"][aria-label*="Facebook"]',
                'a[href*="/facebook.com/"]',
                'div[data-testid="story_header"] a',
                'h2 a'
            ]

            for selector in author_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text:
                        content['author_name'] = element.text.strip()
                        content['author_url'] = element.get_attribute('href')
                        break
                except:
                    continue

            # Lấy thời gian đăng
            time_selectors = [
                'span[data-testid="story_timestamp"]',
                'a[aria-label*="Posted"]',
                'abbr[data-utime]',
                'a[class*="timestamp"]'
            ]

            for selector in time_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text:
                        content['post_time'] = element.text.strip()
                        break
                except:
                    continue

            # Lấy số lượng reaction, comment, share
            self._extract_post_stats(content)

        except Exception as e:
            logger.warning(f"Không thể extract video content: {e}")

        return content

    def _extract_photo_content(self) -> Dict:
        """Trích xuất nội dung photo post"""
        content = {}

        try:
            # Tìm caption ảnh
            caption_selectors = [
                'div[data-testid="post_message"]',
                'div[class*="userContent"]',
                'div[data-ad-preview="message"]',
                'div[class*="caption"]',
                'div[role="article"] div[dir="auto"]'
            ]

            for selector in caption_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.text and len(element.text.strip()) > 10:
                            content['full_description'] = element.text.strip()
                            content['full_title'] = element.text[:100] + '...' if len(element.text) > 100 else element.text
                            break
                    if content.get('full_description'):
                        break
                except:
                    continue

            # Lấy tên tác giả
            self._extract_author_info(content)

            # Lấy thời gian
            self._extract_post_time(content)

            # Lấy stats
            self._extract_post_stats(content)

        except Exception as e:
            logger.warning(f"Không thể extract photo content: {e}")

        return content

    def _extract_text_content(self) -> Dict:
        """Trích xuất nội dung text post"""
        content = {}

        try:
            # Tìm nội dung bài post
            content_selectors = [
                'div[data-testid="post_message"]',
                'div[class*="userContent"]',
                'div[data-ad-preview="message"]',
                'div[role="article"]',
                'div[dir="auto"][class*="text"]'
            ]

            for selector in content_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text:
                        full_text = element.text.strip()
                        content['full_text'] = full_text

                        # Tách thành title và description
                        lines = full_text.split('\n')
                        if lines:
                            content['full_title'] = lines[0][:200]
                            if len(lines) > 1:
                                content['full_description'] = '\n'.join(lines[1:])[:500]
                            else:
                                content['full_description'] = lines[0][:500]
                        break
                except:
                    continue

            # Lấy author và time
            self._extract_author_info(content)
            self._extract_post_time(content)
            self._extract_post_stats(content)

            # Trích xuất hashtag và mentions
            self._extract_tags_and_mentions(content)

        except Exception as e:
            logger.warning(f"Không thể extract text content: {e}")

        return content

    def _extract_share_content(self) -> Dict:
        """Trích xuất nội dung share post"""
        content = {}

        try:
            # Tìm nội dung share
            share_selectors = [
                'div[data-testid="story_message"]',
                'div[class*="shared_content"]',
                'div[role="article"] div[dir="auto"]'
            ]

            for selector in share_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text:
                        content['full_text'] = element.text.strip()
                        break
                except:
                    continue

            # Tìm nội dung gốc được share
            original_selectors = [
                'div[data-testid="shared_story"]',
                'div[class*="shared_post"]',
                'div[data-ft*="original_content"]'
            ]

            for selector in original_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text:
                        content['shared_content'] = element.text.strip()
                        break
                except:
                    continue

            self._extract_author_info(content)
            self._extract_post_time(content)
            self._extract_post_stats(content)

        except Exception as e:
            logger.warning(f"Không thể extract share content: {e}")

        return content

    def _extract_general_content(self) -> Dict:
        """Trích xuất nội dung tổng quát"""
        content = {}

        try:
            # Thử tìm tất cả nội dung text quan trọng
            all_text_elements = self.driver.find_elements(By.CSS_SELECTOR,
                'div[role="article"], div[data-testid*="post"], div[class*="content"]')

            texts = []
            for element in all_text_elements:
                if element.text and len(element.text.strip()) > 20:
                    texts.append(element.text.strip())

            if texts:
                content['full_text'] = '\n\n'.join(texts)

                # Tạo title và description từ nội dung
                first_text = texts[0]
                if len(first_text) > 100:
                    content['full_title'] = first_text[:100] + '...'
                    content['full_description'] = first_text[:500] + '...' if len(first_text) > 500 else first_text
                else:
                    content['full_title'] = first_text
                    content['full_description'] = first_text

            self._extract_author_info(content)
            self._extract_post_time(content)

        except Exception as e:
            logger.warning(f"Không thể extract general content: {e}")

        return content

    def _extract_author_info(self, content: Dict):
        """Trích xuất thông tin tác giả"""
        try:
            author_selectors = [
                'a[role="link"][aria-label*="Facebook"]',
                'a[href*="/facebook.com/"]',
                'div[data-testid="story_header"] a',
                'h2 a',
                'a[class*="actor"]'
            ]

            for selector in author_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text and not content.get('author_name'):
                        content['author_name'] = element.text.strip()
                        content['author_url'] = element.get_attribute('href')
                        break
                except:
                    continue
        except:
            pass

    def _extract_post_time(self, content: Dict):
        """Trích xuất thời gian đăng"""
        try:
            time_selectors = [
                'span[data-testid="story_timestamp"]',
                'a[aria-label*="Posted"]',
                'abbr[data-utime]',
                'a[class*="timestamp"]',
                'span[class*="timestamp"]'
            ]

            for selector in time_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text and not content.get('post_time'):
                        content['post_time'] = element.text.strip()
                        break
                except:
                    continue
        except:
            pass

    def _extract_post_stats(self, content: Dict):
        """Trích xuất số lượng reactions, comments, shares"""
        try:
            # Reactions
            reaction_selectors = [
                'span[data-testid="UFI2ReactionsCount"]',
                'span[class*="reactionsCount"]',
                'a[aria-label*="reaction"]',
                'div[aria-label*="reaction"]'
            ]

            for selector in reaction_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text:
                        content['reactions_count'] = element.text.strip()
                        break
                except:
                    continue

            # Comments
            comment_selectors = [
                'span[data-testid="UFI2CommentsCount"]',
                'a[aria-label*="comment"]',
                'span[class*="comment"]'
            ]

            for selector in comment_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text:
                        content['comments_count'] = element.text.strip()
                        break
                except:
                    continue

            # Shares
            share_selectors = [
                'span[data-testid="UFI2SharesCount"]',
                'a[aria-label*="share"]',
                'span[class*="share"]'
            ]

            for selector in share_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text:
                        content['shares_count'] = element.text.strip()
                        break
                except:
                    continue
        except:
            pass

    def _extract_tags_and_mentions(self, content: Dict):
        """Trích xuất hashtag và mentions"""
        try:
            if content.get('full_text'):
                text = content['full_text']

                # Hashtags
                hashtags = re.findall(r'#(\w+)', text)
                if hashtags:
                    content['hashtags'] = hashtags

                # Mentions (@username)
                mentions = re.findall(r'@(\w+)', text)
                if mentions:
                    content['mentions'] = mentions

                # Links
                links = re.findall(r'https?://\S+', text)
                if links:
                    content['links'] = links
        except:
            pass

    def _extract_metadata_from_html(self, html_content: str) -> Dict:
        """Trích xuất metadata từ HTML (bổ sung)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        metadata = {}

        try:
            # Tìm thẻ title
            title_tag = soup.find('title')
            if title_tag and title_tag.text:
                metadata['page_title'] = title_tag.text.strip()

            # Tìm meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                metadata['meta_description'] = meta_desc['content']

            # Tìm tất cả text có thể là nội dung
            potential_content = []

            # Các selector có thể chứa nội dung
            content_selectors = [
                'div[data-testid="post_message"]',
                'div[class*="userContent"]',
                'div[role="article"]',
                'div[dir="auto"]',
                'p',
                'span',
                'div'
            ]

            for selector in content_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text and len(text) > 50 and text not in potential_content:
                        potential_content.append(text)

            if potential_content:
                # Sắp xếp theo độ dài (thường nội dung dài nhất là nội dung chính)
                potential_content.sort(key=len, reverse=True)
                metadata['potential_contents'] = potential_content[:3]  # Lấy 3 nội dung dài nhất

        except Exception as e:
            logger.warning(f"Không thể extract metadata từ HTML: {e}")

        return metadata

    def _clean_content(self, content: Dict) -> Dict:
        """Làm sạch và chuẩn hóa nội dung"""
        cleaned = content.copy()

        # Loại bỏ các trường rỗng
        for key in list(cleaned.keys()):
            if isinstance(cleaned[key], str) and not cleaned[key].strip():
                cleaned[key] = ''
            elif isinstance(cleaned[key], list) and not cleaned[key]:
                cleaned[key] = []

        # Giới hạn độ dài
        if cleaned.get('full_title') and len(cleaned['full_title']) > 200:
            cleaned['full_title'] = cleaned['full_title'][:197] + '...'

        if cleaned.get('full_description') and len(cleaned['full_description']) > 1000:
            cleaned['full_description'] = cleaned['full_description'][:997] + '...'

        if cleaned.get('full_text') and len(cleaned['full_text']) > 5000:
            cleaned['full_text'] = cleaned['full_text'][:4997] + '...'

        return cleaned

    def get_full_content(self, url: str, timeout: int = 40) -> Dict:
        """
        Lấy FULL nội dung từ URL Facebook

        Returns:
            Dict chứa full content và metadata
        """
        result = {
            'success': False,
            'error': None,
            'url': url,
            'content': {},
            'metadata': {},
            'method': 'selenium'
        }

        try:
            # Luôn dùng Selenium để lấy full content
            if not self.use_selenium:
                logger.warning("Selenium được khuyến nghị để lấy full content")

            # Lấy full content bằng Selenium
            full_content = self.extract_full_content_selenium(url, timeout)

            # Lấy thêm metadata OG (dùng requests cho nhanh)
            try:
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    metadata = self._extract_og_metadata(response.text)
                    result['metadata'] = metadata
            except:
                pass

            # Gộp kết quả
            result['content'] = full_content

            # Kiểm tra xem có lấy được nội dung không
            if any([full_content.get('full_title'),
                    full_content.get('full_description'),
                    full_content.get('full_text')]):
                result['success'] = True
            else:
                result['error'] = 'Không tìm thấy nội dung'
                result['success'] = False

        except Exception as e:
            result['error'] = f"Lỗi: {str(e)}"
            logger.error(f"Lỗi khi lấy full content: {e}")

        return result

    def _extract_og_metadata(self, html_content: str) -> Dict:
        """Trích xuất OG metadata cơ bản"""
        soup = BeautifulSoup(html_content, 'html.parser')
        metadata = {}

        # Lấy OG metadata
        og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
        for tag in og_tags:
            prop = tag.get('property', '').replace('og:', '')
            content = tag.get('content', '')
            if content:
                metadata[prop] = content

        return metadata

    def cleanup(self):
        """Dọn dẹp tài nguyên"""
        self.close_selenium_driver()
        self.session.close()


# Sử dụng
if __name__ == "__main__":
    # Khởi tạo extractor
    extractor = FacebookContentExtractor(use_selenium=True, headless=True)

    test_urls = [
        "https://www.facebook.com/share/p/19FTEP281g/",
        "https://www.facebook.com/photo/?fbid=122116530465046735&set=gm.1482479739506865&idorvanity=440881430333373",
        "https://www.facebook.com/reel/703809526002594",
        # Thêm các URL khác để test
    ]

    try:
        for url in test_urls:
            print(f"\n{'='*80}")
            print(f"📱 Đang phân tích: {url}")
            print(f"{'='*80}")

            result = extractor.get_full_content(url, timeout=40)

            if result['success']:
                content = result['content']
                metadata = result['metadata']

                print("✅ Lấy thành công FULL CONTENT!")

                # Hiển thị full content
                if content.get('full_title'):
                    print(f"\n📌 FULL TITLE: {content['full_title']}")

                if content.get('full_description'):
                    print(f"\n📝 FULL DESCRIPTION: {content['full_description']}")

                if content.get('full_text'):
                    print(f"\n📄 FULL TEXT ({len(content['full_text'])} chars):")
                    print(f"{content['full_text'][:500]}..." if len(content['full_text']) > 500 else content['full_text'])

                if content.get('author_name'):
                    print(f"\n👤 Tác giả: {content['author_name']}")

                if content.get('post_time'):
                    print(f"⏰ Thời gian: {content['post_time']}")

                # Hiển thị stats
                if any([content.get('reactions_count'),
                        content.get('comments_count'),
                        content.get('shares_count')]):
                    print(f"\n📊 Thống kê:")
                    if content.get('reactions_count'):
                        print(f"  ❤️  Reactions: {content['reactions_count']}")
                    if content.get('comments_count'):
                        print(f"  💬 Comments: {content['comments_count']}")
                    if content.get('shares_count'):
                        print(f"  🔄 Shares: {content['shares_count']}")

                # Hiển thị metadata OG (để so sánh)
                if metadata:
                    print(f"\n🔍 OG Metadata (bị cắt xén):")
                    if metadata.get('title'):
                        print(f"  Title: {metadata['title']}")
                    if metadata.get('description'):
                        print(f"  Description: {metadata['description'][:100]}...")

                # So sánh độ dài
                if content.get('full_description') and metadata.get('description'):
                    og_len = len(metadata['description'])
                    full_len = len(content['full_description'])
                    print(f"\n📏 So sánh: OG Description: {og_len} chars | Full Description: {full_len} chars")
                    print(f"   Chênh lệch: {full_len - og_len} chars")

            else:
                print(f"❌ Thất bại: {result.get('error', 'Unknown error')}")

            print(f"\n⏳ Đợi 3 giây trước khi xử lý URL tiếp theo...")
            time.sleep(3)

    finally:
        extractor.cleanup()
        print("\n✨ Hoàn thành!")