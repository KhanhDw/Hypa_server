# -*- coding: utf-8 -*-
"""
Test script to verify the improved scraper functionality with metrics
"""
import asyncio
import os
from app.services.facebook.product import AsyncFacebookScraperStreaming
from app.services.facebook.product.metrics import (
    FACEBOOK_SCRAPES_TOTAL,
    FACEBOOK_SCRAPES_SUCCESS,
    FACEBOOK_SCRAPES_FAILED,
    FACEBOOK_RATE_LIMITS,
    FACEBOOK_CHECKPOINTS,
    FACEBOOK_CACHE_HITS,
    FACEBOOK_CACHE_MISSES,
    FACEBOOK_NAVIGATION_DURATION,
    FACEBOOK_EXTRACTION_DURATION,
    FACEBOOK_SCRAPE_DURATION,
    FACEBOOK_ACTIVE_CONTEXTS,
    FACEBOOK_ACTIVE_PAGES
)

async def test_scraper():
    # Configuration for testing
    scraper_config = {
        'headless': True,
        'max_concurrent': 3,
        'cache_ttl': 300,
        'enable_images': False,  # Disable images to speed up
        'mode': 'simple',  # Start with simple mode
        'use_browser_pool': True,
        'max_pages_per_context': 5,
        'max_contexts': 3,
        'context_reuse_limit': 15
    }

    async with AsyncFacebookScraperStreaming(**scraper_config) as scraper:
        # Test URLs from the linkTest.md file
        test_urls = [
            "https://www.facebook.com/share/p/19FTEP281g/",
            "https://www.facebook.com/reel/703809526002594"
        ]

        print("Testing single URL scraping...")
        for url in test_urls:
            print(f"Scraping: {url}")
            try:
                result = await scraper.get_facebook_metadata(url)
                print(f"Result keys: {list(result.keys())}")
                print(f"Success: {result.get('success')}")
                print(f"Title: {result.get('title', 'N/A')[:50]}...")
                print(f"Description: {result.get('description', 'N/A')[:50]}...")
                print(f"Scrape time: {result.get('scrape_time', 0):.2f}s")
                print(f"Navigation time: {result.get('navigation_time', 0):.2f}s")
                if result.get('error'):
                    print(f"Error: {result.get('error')}")
                print("---")
            except Exception as e:
                print(f"Exception for {url}: {str(e)}")
                print("---")

        print("\nTesting multiple URL scraping...")
        try:
            results = await scraper.get_multiple_metadata(test_urls[:1])  # Just test with one to avoid rate limits
            print(f"Multiple results: {len(results)} items")
        except Exception as e:
            print(f"Multiple scraping error: {str(e)}")

        # Print metrics after testing
        print("\n--- METRICS SUMMARY ---")
        from prometheus_client import REGISTRY
        
        # Get all metrics
        for metric in REGISTRY.collect():
            if metric.name.startswith('facebook_'):
                for sample in metric.samples:
                    print(f"{sample.name}: {sample.value}")

if __name__ == "__main__":
    asyncio.run(test_scraper())