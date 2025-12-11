import asyncio
from playwright.async_api import async_playwright

async def get_facebook_metadata_async(url):
    """
    Lấy metadata từ Facebook sử dụng async
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        try:
            # Điều hướng
            await page.goto(url, wait_until="networkidle")

            # Chờ và lấy metadata
            metadata = {
                'url': url,
                'title': await page.title(),
                'og_data': {}
            }

            # Lấy các thẻ meta
            meta_elements = await page.query_selector_all('meta')

            for element in meta_elements:
                property_name = await element.get_attribute('property') or await element.get_attribute('name')
                content = await element.get_attribute('content')

                if property_name and content and property_name.startswith('og:'):
                    key = property_name.replace('og:', '')
                    metadata['og_data'][key] = content

            return metadata

        finally:
            await browser.close()

# Sử dụng async
async def main():
    url = "https://www.facebook.com/share/p/19FTEP281g/"
    metadata = await get_facebook_metadata_async(url)
    print(metadata)

# Chạy async
asyncio.run(main())