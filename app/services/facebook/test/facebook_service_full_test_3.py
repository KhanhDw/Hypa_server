from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json

def get_facebook_metadata_with_bs(url):
    """
    Lấy metadata từ Facebook kết hợp BeautifulSoup
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            # Dùng headless=False có thể bypass một số detection
            # headless=True dễ bị phát hiện hơn
            args=[
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
        )

        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )

        # Thêm header để tránh bị chặn
        context.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        page = context.new_page()

        try:
            # Điều hướng đến URL
            print(f"Đang truy cập Facebook: {url}")
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Kiểm tra response
            if response and response.status != 200:
                print(f"Lỗi HTTP: {response.status}")
                return None

            # Chờ và cuộn trang
            page.wait_for_load_state('networkidle')
            page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            # Lấy HTML content
            html_content = page.content()

            # Parse với BeautifulSoup
            soup = BeautifulSoup(html_content, 'lxml')

            # Khởi tạo metadata dict
            metadata = {
                'url': url,
                'title': None,
                'description': None,
                'images': [],
                'videos': [],
                'og_data': {},
                'twitter_data': {},
                'basic_meta': {}
            }

            # Lấy title
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.get_text(strip=True)

            # Lấy các thẻ meta
            for meta in soup.find_all('meta'):
                attrs = meta.attrs

                # Open Graph tags
                if 'property' in attrs and attrs['property'].startswith('og:'):
                    key = attrs['property'].replace('og:', '')
                    metadata['og_data'][key] = attrs.get('content', '')

                # Twitter Card tags
                elif 'property' in attrs and attrs['property'].startswith('twitter:'):
                    key = attrs['property'].replace('twitter:', '')
                    metadata['twitter_data'][key] = attrs.get('content', '')

                # Basic meta tags
                elif 'name' in attrs:
                    metadata['basic_meta'][attrs['name']] = attrs.get('content', '')

            # Lấy hình ảnh
            for img in soup.find_all('img', src=True):
                src = img['src']
                if src and (src.startswith('http') or src.startswith('//')):
                    if src.startswith('//'):
                        src = 'https:' + src
                    metadata['images'].append(src)

            # Lấy video
            for video in soup.find_all('video', src=True):
                src = video['src']
                if src:
                    metadata['videos'].append(src)

            # Lấy JSON-LD
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            if json_ld_scripts:
                metadata['json_ld'] = []
                for script in json_ld_scripts:
                    try:
                        data = json.loads(script.string)
                        metadata['json_ld'].append(data)
                    except:
                        continue

            return metadata

        except Exception as e:
            print(f"Lỗi: {str(e)}")
            return None

        finally:
            browser.close()

# Sử dụng
if __name__ == "__main__":
    url = "https://www.facebook.com/share/p/1DBEn8zzrM/"
    metadata = get_facebook_metadata_with_bs(url)

    if metadata:
        print("Metadata lấy được:")
        print(json.dumps(metadata, indent=2, ensure_ascii=False))