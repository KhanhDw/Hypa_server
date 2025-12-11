from playwright.sync_api import sync_playwright
from playwright_stealth import stealth
import time
import random
import json

class FacebookScraperWithStealth:
    def __init__(self, headless=True):
        self.headless = headless
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

    def get_facebook_metadata(self, url):
        """Lấy metadata từ Facebook sử dụng playwright-stealth"""
        with sync_playwright() as p:
            # Cấu hình browser arguments
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--window-size=1920,1080',
                '--start-maximized',
                '--disable-extensions',
                '--disable-gpu',
                '--disable-software-rasterizer',
            ]

            if self.headless:
                browser_args.append('--headless=new')

            browser = p.chromium.launch(
                headless=self.headless,
                args=browser_args,
                # Nếu có Chrome thật, dùng channel
                channel='chrome' if not self.headless else None
            )

            # Chọn user-agent ngẫu nhiên
            user_agent = random.choice(self.user_agents)

            # Tạo context
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                locale='vi-VN',
                timezone_id='Asia/Ho_Chi_Minh',
                geolocation={'latitude': 10.8231, 'longitude': 106.6297},
                permissions=['geolocation'],
                color_scheme='light',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            )

            page = context.new_page()

            try:
                # Áp dụng stealth - QUAN TRỌNG: gọi trước khi goto()
                stealth(page)
                print("Đã áp dụng stealth")

                # Điều hướng đến URL
                print(f"Đang truy cập: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Chờ trang tải
                time.sleep(random.uniform(2, 4))

                # Cuộn trang để tải thêm nội dung
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                time.sleep(random.uniform(1, 2))
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(random.uniform(1, 2))

                # Kiểm tra xem có bị chuyển hướng đến login không
                current_url = page.url
                if 'login' in current_url or 'checkpoint' in current_url:
                    print("Bị chuyển hướng đến trang login")
                    return None

                # Lấy metadata
                metadata = self.extract_metadata(page)
                metadata['url'] = url
                metadata['final_url'] = current_url

                return metadata

            except Exception as e:
                print(f"Lỗi: {str(e)}")

                # Debug: lưu screenshot nếu không headless
                if not self.headless:
                    page.screenshot(path='debug_error.png')

                return None

            finally:
                browser.close()

    def extract_metadata(self, page):
        """Trích xuất metadata từ page"""
        return page.evaluate("""() => {
            const metadata = {
                title: document.title,
                og: {},
                twitter: {},
                meta: {},
                images: [],
                jsonLd: []
            };

            // Lấy tất cả meta tags
            const metas = document.querySelectorAll('meta');
            metas.forEach(meta => {
                const property = meta.getAttribute('property');
                const name = meta.getAttribute('name');
                const content = meta.getAttribute('content');

                if (!content) return;

                if (property) {
                    if (property.startsWith('og:')) {
                        metadata.og[property.replace('og:', '')] = content;
                    } else if (property.startsWith('twitter:')) {
                        metadata.twitter[property.replace('twitter:', '')] = content;
                    }
                }

                if (name) {
                    metadata.meta[name] = content;
                }
            });

            // Lấy hình ảnh
            const imgs = document.querySelectorAll('img[src]');
            imgs.forEach(img => {
                const src = img.src;
                if (src && src.startsWith('http')) {
                    metadata.images.push(src);
                }
            });

            // Lấy JSON-LD
            const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
            jsonLdScripts.forEach(script => {
                try {
                    metadata.jsonLd.push(JSON.parse(script.textContent));
                } catch(e) {
                    // Ignore parse errors
                }
            });

            return metadata;
        }""")

# Test function
def test_facebook_scraper():
    """Test scraper với các URL Facebook"""
    scraper = FacebookScraperWithStealth(headless=False)  # Dùng headless=False để debug

    # Test URLs
    test_urls = [
        "https://www.facebook.com/share/v/1HU8Kjpa9j/",
    ]

    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print(f"{'='*60}")

        metadata = scraper.get_facebook_metadata(url)

        if metadata:
            print("\n✅ Metadata lấy được:")
            print(f"Title: {metadata.get('title', 'N/A')}")
            print(f"Final URL: {metadata.get('final_url', 'N/A')}")

            if metadata.get('og'):
                print("\nOpen Graph Data:")
                for key, value in metadata['og'].items():
                    print(f"  {key}: {value[:100]}{'...' if len(value) > 100 else ''}")

            if metadata.get('meta', {}).get('description'):
                print(f"\nDescription: {metadata['meta']['description'][:150]}...")

            # Lưu kết quả ra file JSON
            with open(f'facebook_metadata_{int(time.time())}.json', 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            print(f"\n✅ Đã lưu kết quả ra file JSON")
        else:
            print("\n❌ Không thể lấy metadata")

        # Delay giữa các request
        delay = random.uniform(5, 10)
        print(f"\n⏳ Đợi {delay:.1f} giây trước request tiếp theo...")
        time.sleep(delay)

if __name__ == "__main__":
    test_facebook_scraper()