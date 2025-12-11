from playwright.sync_api import sync_playwright
import json
import time

def get_facebook_metadata(url):
    """
    Lấy metadata từ trang Facebook sử dụng Playwright
    """
    with sync_playwright() as p:
        # Khởi tạo browser
        browser = p.chromium.launch(
            headless=True,
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
        )  # Có thể đổi thành False để debug
        context = browser.new_context(
             viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
            # Điều hướng đến URL
            print(f"Đang truy cập: {url}")
            page.goto(url, wait_until="networkidle", timeout=60000)

            # Chờ trang tải hoàn tất
            time.sleep(3)

            # Cuộn trang để tải thêm nội dung
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

            # Lấy metadata từ thẻ meta
            metadata = {
                'url': url,
                'title': page.title(),
                'description': None,
                'image': None,
                'type': None,
                'site_name': None,
                'og_data': {},
                'basic_meta': {}
            }

            # Lấy tất cả thẻ meta
            meta_tags = page.query_selector_all('meta')

            for tag in meta_tags:
                property_name = tag.get_attribute('property') or tag.get_attribute('name')
                content = tag.get_attribute('content')

                if property_name and content:
                    # Thu thập Open Graph data
                    if property_name.startswith('og:'):
                        key = property_name.replace('og:', '')
                        metadata['og_data'][key] = content

                        # Gán vào các trường chính
                        if key == 'title':
                            metadata['title'] = content
                        elif key == 'description':
                            metadata['description'] = content
                        elif key == 'image':
                            metadata['image'] = content
                        elif key == 'type':
                            metadata['type'] = content
                        elif key == 'site_name':
                            metadata['site_name'] = content

                    # Thu thập các meta khác
                    elif property_name in ['description', 'keywords', 'author']:
                        metadata['basic_meta'][property_name] = content

            # Lấy thông tin từ JSON-LD nếu có
            try:
                json_ld_scripts = page.query_selector_all('script[type="application/ld+json"]')
                json_ld_data = []
                for script in json_ld_scripts:
                    try:
                        content = script.inner_text()
                        if content:
                            json_ld_data.append(json.loads(content))
                    except:
                        continue

                if json_ld_data:
                    metadata['json_ld'] = json_ld_data
            except:
                pass

            return metadata

        except Exception as e:
            print(f"Lỗi khi lấy dữ liệu: {e}")
            return None

        finally:
            browser.close()

# Sử dụng
if __name__ == "__main__":
    url = "https://www.facebook.com/share/p/19FTEP281g/"  # Thay bằng URL thực tế
    metadata = get_facebook_metadata(url)

    if metadata:
        print("Metadata lấy được:")
        print(json.dumps(metadata, indent=2, ensure_ascii=False))