import asyncio
from async_facebook_scraper import AsyncFacebookScraper
from fast_facebook_scraper import FastFacebookScraper

async def mainA():
    scraper = AsyncFacebookScraper(headless=True)
    url1 = [
        "https://www.facebook.com/share/p/1HMEAngzqM/",
        "https://www.facebook.com/share/p/14PkMdwKj5P/",
        "https://www.facebook.com/share/p/17gQ6Lg5Pf/",
        "https://www.facebook.com/share/p/16Zfzau1N1/",
        "https://www.facebook.com/share/p/1G45H7VBja/",
    ]

    print("Đang lấy dữ liệu từ Facebook...")
    # data = await scraper.get_facebook_metadata(url1)
    data = await scraper.get_multiple_metadata(url1)

    print("\n=== KẾT QUẢ ===")
    print("------->", data)

def main():
    scraper = FastFacebookScraper(headless=True)
    url1 = "https://www.facebook.com/share/p/1HMEAngzqM/"

    print("Đang lấy dữ liệu từ Facebook...")
    data = scraper.get_facebook_metadata(url1)

    print("\n=== KẾT QUẢ ===")
    print("------->", data)

if __name__ == "__main__":
    # Correctly run the async main function using asyncio.run()
    asyncio.run(mainA()) # chốt cái này
    # main()