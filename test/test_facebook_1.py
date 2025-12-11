# tests/test_facebook_scraper_service.py
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
# NOTE: The original FacebookScraperService has been replaced with AsyncFacebookScraperStreaming
# The test methods in this file need to be updated to match the new API
# from app.services.facebook.product.scraper_core import AsyncFacebookScraperStreaming
from playwright.async_api import Page, BrowserContext
import json


# ==================== FIXTURES ====================
@pytest.fixture
def sample_config():
    """Fixture cung cấp config mẫu cho testing"""
    return {
        'headless': True,
        'max_concurrent': 2,
        'cache_ttl': 30,  # 30 giây để test cache
        'enable_images': False,
        'timeout': 5000,
        'user_agents': [
            'Test-Agent-1',
            'Test-Agent-2'
        ]
    }


# Note: Original FacebookScraperService no longer exists, this test file needs to be updated for new service API
# @pytest.fixture
# def scraper_service(sample_config):
#     """Fixture tạo instance của service"""
#     return AsyncFacebookScraperStreaming(**sample_config)


@pytest.fixture
def mock_page():
    """Fixture tạo mock Page object"""
    page = AsyncMock(spec=Page)

    # Mock các phương thức cần thiết
    page.evaluate = AsyncMock()
    page.set_default_navigation_timeout = AsyncMock()
    page.set_default_timeout = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.close = AsyncMock()
    page.route = AsyncMock()

    return page


@pytest.fixture
def mock_context(mock_page):
    """Fixture tạo mock Context object"""
    context = AsyncMock(spec=BrowserContext)
    context.new_page = AsyncMock(return_value=mock_page)
    context.close = AsyncMock()
    return context


@pytest.fixture
def mock_browser(mock_context):
    """Fixture tạo mock Browser object"""
    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=mock_context)
    return browser


@pytest.fixture
def sample_facebook_urls():
    """Fixture cung cấp URLs mẫu để test"""
    return [
        'https://www.facebook.com/username/posts/123456789',
        'https://www.facebook.com/groups/groupname/permalink/987654321/',
        'https://m.facebook.com/story.php?story_fbid=111222333',
        'https://fb.watch/abc123xyz/'
    ]


@pytest.fixture
def sample_metadata():
    """Fixture cung cấp metadata mẫu"""
    return {
        'title': 'Test Post Title',
        'description': 'This is a test post description',
        'image': 'https://facebook.com/image.jpg',
        'url': 'https://www.facebook.com/test/post',
        'og_data': {'title': 'OG Title'},
        'twitter_data': {'card': 'summary'},
        'meta_tags': {'og:title': 'Test'},
        'images': [{'src': 'img1.jpg', 'alt': ''}],
        'videos': [],
        'page_info': {'url': 'test', 'language': 'en'},
        'success': True
    }


# ==================== UNIT TESTS ====================
class TestFacebookScraperServiceUnit:
    """Test suite cho các phương thức đơn vị"""

    def test_init_with_default_config(self):
        """Test khởi tạo với config mặc định"""
        # When
        service = FacebookScraperService()

        # Then
        assert service.config['headless'] == True
        assert service.config['max_concurrent'] == 5
        assert service.config['cache_ttl'] == 300
        assert service.config['enable_images'] == False
        assert len(service.config['user_agents']) > 0

    def test_init_with_custom_config(self, sample_config):
        """Test khởi tạo với config custom"""
        # Given
        custom_config = {**sample_config, 'headless': False}

        # When
        service = FacebookScraperService(custom_config)

        # Then
        assert service.config['headless'] == False
        assert service._semaphore._value == custom_config['max_concurrent']

    def test_get_cache_key(self, scraper_service):
        """Test thuật toán tạo cache key"""
        # Given
        url = 'https://www.facebook.com/test'

        # When
        cache_key = scraper_service._get_cache_key(url)

        # Then
        assert isinstance(cache_key, str)
        assert len(cache_key) == 12  # md5[:12]
        # Same URL nên có cùng cache key
        assert cache_key == scraper_service._get_cache_key(url)

    def test_get_random_user_agent(self, scraper_service):
        """Test thuật toán chọn user agent"""
        # When
        ua1 = scraper_service._get_random_user_agent()
        ua2 = scraper_service._get_random_user_agent()

        # Then
        assert ua1 in scraper_service.config['user_agents']
        assert ua2 in scraper_service.config['user_agents']
        # Kiểm tra usage tracking
        assert scraper_service.ua_usage[ua1] > 0

    def test_validate_facebook_url_valid(self, scraper_service):
        """Test validate URL hợp lệ"""
        # Given
        valid_urls = [
            'https://www.facebook.com/test',
            'https://facebook.com/test',
            'http://m.facebook.com/test',
            'https://fb.com/test',
            'https://fb.watch/abc123'
        ]

        # When & Then
        for url in valid_urls:
            assert scraper_service.validate_facebook_url(url) == True

    def test_validate_facebook_url_invalid(self, scraper_service):
        """Test validate URL không hợp lệ"""
        # Given
        invalid_urls = [
            'https://google.com',
            'https://twitter.com/test',
            '',
            'facebook.com/test',  # Thiếu protocol
            'ftp://facebook.com/test'
        ]

        # When & Then
        for url in invalid_urls:
            assert scraper_service.validate_facebook_url(url) == False

    def test_extract_facebook_post_id(self, scraper_service):
        """Test extract post ID từ URL"""
        test_cases = [
            ('https://www.facebook.com/posts/123456789', '123456789'),
            ('https://facebook.com/groups/123/permalink/987654321/', '987654321'),
            ('https://m.facebook.com/story.php?story_fbid=111222333', '111222333'),
            ('https://facebook.com/photo.php?fbid=444555666', '444555666'),
            ('https://facebook.com/share/p/abc123', 'abc123'),
            ('https://facebook.com/test', None),  # Không có post ID
        ]

        for url, expected_id in test_cases:
            # When
            result = scraper_service.extract_facebook_post_id(url)

            # Then
            assert result == expected_id, f"Failed for URL: {url}"

    def test_format_metadata_for_display(self, scraper_service, sample_metadata):
        """Test format metadata cho display"""
        # When
        formatted = scraper_service.format_metadata_for_display(sample_metadata)

        # Then
        assert 'URL:' in formatted
        assert 'Title:' in formatted
        assert 'Test Post Title' in formatted
        assert 'From cache:' in formatted

    def test_format_metadata_error(self, scraper_service):
        """Test format metadata khi có error"""
        # Given
        error_metadata = {
            'success': False,
            'error': 'Test error message'
        }

        # When
        formatted = scraper_service.format_metadata_for_display(error_metadata)

        # Then
        assert 'Error:' in formatted
        assert 'Test error message' in formatted

    def test_cleanup_old_cache(self, scraper_service):
        """Test cleanup cache cũ"""
        # Given
        old_timestamp = time.time() - 1000  # Cũ hơn cache_ttl
        current_timestamp = time.time()

        scraper_service._cache = {
            'key1': {'data': {}, 'timestamp': old_timestamp},
            'key2': {'data': {}, 'timestamp': current_timestamp}
        }

        # When
        scraper_service._cleanup_old_cache()

        # Then
        assert 'key1' not in scraper_service._cache
        assert 'key2' in scraper_service._cache

    def test_get_optimized_browser_args(self, scraper_service):
        """Test tạo browser args"""
        # When
        args = scraper_service._get_optimized_browser_args()

        # Then
        assert '--disable-blink-features=AutomationControlled' in args
        assert '--no-sandbox' in args

        # Test với enable_images = True
        scraper_service.config['enable_images'] = True
        args_with_images = scraper_service._get_optimized_browser_args()
        assert '--blink-settings=imagesEnabled=false' not in args_with_images


# ==================== ASYNC UNIT TESTS ====================
@pytest.mark.asyncio
class TestFacebookScraperServiceAsync:
    """Test suite cho các phương thức async"""

    async def test_initialize_and_close(self, scraper_service, mock_browser):
        """Test khởi tạo và đóng browser"""
        with patch('app.services.facebook.facebook_scraper_service.async_playwright') as mock_playwright:
            # Setup
            mock_pw_instance = AsyncMock()
            mock_pw_instance.chromium = AsyncMock()
            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

            # When
            await scraper_service.initialize()

            # Then
            assert scraper_service.playwright is not None
            assert scraper_service.browser is not None
            mock_pw_instance.chromium.launch.assert_called_once()

            # Test close
            await scraper_service.close()
            mock_browser.close.assert_called_once()
            mock_pw_instance.stop.assert_called_once()

    async def test_scrape_single_url_cache_hit(self, scraper_service, sample_facebook_urls):
        """Test scrape với cache hit"""
        # Given
        url = sample_facebook_urls[0]
        cache_key = scraper_service._get_cache_key(url)
        cached_data = {
            'data': {'url': url, 'success': True, 'title': 'Cached Title'},
            'timestamp': time.time()  # Vẫn còn hiệu lực
        }
        scraper_service._cache[cache_key] = cached_data

        # When
        result = await scraper_service.scrape_single_url(url)

        # Then
        assert result['from_cache'] == True
        assert result['title'] == 'Cached Title'
        assert 'scrape_time' in result

    async def test_scrape_single_url_cache_expired(self, scraper_service, sample_facebook_urls, mock_browser):
        """Test scrape với cache đã hết hạn"""
        # Given
        url = sample_facebook_urls[0]
        cache_key = scraper_service._get_cache_key(url)
        cached_data = {
            'data': {'url': url, 'success': True, 'title': 'Expired Cache'},
            'timestamp': time.time() - 1000  # Đã hết hạn
        }
        scraper_service._cache[cache_key] = cached_data

        with patch.object(scraper_service, '_execute_scraping_algorithm') as mock_execute:
            mock_execute.return_value = {
                'url': url,
                'success': True,
                'title': 'Fresh Data'
            }

            # When
            result = await scraper_service.scrape_single_url(url)

            # Then
            assert result['from_cache'] == False
            assert result['title'] == 'Fresh Data'
            mock_execute.assert_called_once_with(url)

    async def test_scrape_single_url_success(self, scraper_service, mock_browser, mock_context, mock_page, sample_facebook_urls):
        """Test scrape thành công một URL"""
        # Given
        url = sample_facebook_urls[0]

        with patch.object(scraper_service, 'browser', mock_browser):
            with patch.object(scraper_service, '_get_random_user_agent', return_value='Test-Agent'):
                # Setup mock return values
                mock_page.evaluate.return_value = {
                    'title': 'Test Post',
                    'description': 'Test Description',
                    'success': True
                }

                # When
                result = await scraper_service.scrape_single_url(url)

                # Then
                assert result['success'] == True
                assert result['url'] == url
                assert 'scrape_time' in result

                # Verify browser interactions
                mock_browser.new_context.assert_called_once()
                mock_context.new_page.assert_called_once()
                mock_page.goto.assert_called_once_with(
                    url,
                    wait_until="networkidle",
                    timeout=scraper_service.config['timeout'],
                    referer="https://www.facebook.com/"
                )
                mock_page.close.assert_called_once()

    async def test_scrape_single_url_failure(self, scraper_service, mock_browser, mock_context, mock_page):
        """Test scrape thất bại"""
        # Given
        url = 'https://facebook.com/test'
        mock_page.goto.side_effect = Exception('Navigation timeout')

        with patch.object(scraper_service, 'browser', mock_browser):
            # When
            result = await scraper_service.scrape_single_url(url)

            # Then
            assert result['success'] == False
            assert 'error' in result
            assert 'Navigation timeout' in result['error']

    async def test_scrape_multiple_urls(self, scraper_service, sample_facebook_urls):
        """Test scrape nhiều URLs"""
        with patch.object(scraper_service, 'scrape_single_url') as mock_scrape:
            # Setup
            mock_scrape.side_effect = [
                {'url': sample_facebook_urls[0], 'success': True},
                {'url': sample_facebook_urls[1], 'success': True},
                Exception('Test error'),
                {'url': sample_facebook_urls[3], 'success': True}
            ]

            # When
            results = await scraper_service.scrape_multiple_urls(sample_facebook_urls)

            # Then
            assert len(results) == 4
            assert results[0]['success'] == True
            assert results[2]['success'] == False  # Exception case
            assert 'Test error' in results[2]['error']

    async def test_scrape_urls_streaming(self, scraper_service, sample_facebook_urls):
        """Test scrape streaming"""
        with patch.object(scraper_service, 'scrape_single_url') as mock_scrape:
            # Setup
            mock_scrape.side_effect = [
                {'url': sample_facebook_urls[0], 'success': True},
                {'url': sample_facebook_urls[1], 'success': True},
                Exception('Stream error'),
                {'url': sample_facebook_urls[3], 'success': True}
            ]

            # When
            results = []
            async for result in scraper_service.scrape_urls_streaming(sample_facebook_urls):
                results.append(result)

            # Then
            assert len(results) == 4
            assert results[0]['success'] == True
            assert results[2]['success'] == False
            assert results[3]['success'] == True

    async def test_extract_metadata_algorithm(self, scraper_service, mock_page):
        """Test thuật toán extract metadata"""
        # Given
        mock_html_content = """
        <html lang="en">
            <head>
                <title>Test Page</title>
                <meta property="og:title" content="OG Title">
                <meta property="og:description" content="OG Description">
                <meta property="og:image" content="https://test.com/image.jpg">
                <meta name="twitter:card" content="summary">
                <script type="application/ld+json">{"@context": "http://schema.org"}</script>
            </head>
            <body>
                <img src="https://test.com/img1.jpg" alt="Image 1">
                <img src="https://test.com/img2.jpg" alt="Image 2">
            </body>
        </html>
        """

        mock_page.evaluate.return_value = {
            'title': 'Test Page',
            'description': 'OG Description',
            'image': 'https://test.com/image.jpg',
            'og_data': {'title': 'OG Title', 'description': 'OG Description'},
            'twitter_data': {'card': 'summary'},
            'meta_tags': {'og:title': 'OG Title'},
            'images': [
                {'src': 'https://test.com/img1.jpg', 'alt': 'Image 1'},
                {'src': 'https://test.com/img2.jpg', 'alt': 'Image 2'}
            ],
            'json_ld': [{'@context': 'http://schema.org'}]
        }

        # When
        result = await scraper_service._extract_metadata_algorithm(mock_page)

        # Then
        assert result['title'] == 'Test Page'
        assert result['description'] == 'OG Description'
        assert len(result['images']) == 2
        assert len(result['json_ld']) == 1

    async def test_create_route_handler_without_images(self, scraper_service):
        """Test route handler khi disable images"""
        # Given
        scraper_service.config['enable_images'] = False

        # When
        handler = scraper_service._create_route_handler()

        # Test với các resource types khác nhau
        mock_route = AsyncMock()
        mock_route.request.resource_type = "image"

        # Then: Image nên bị abort
        await handler(mock_route)
        mock_route.abort.assert_called_once()

    async def test_create_route_handler_with_images(self, scraper_service):
        """Test route handler khi enable images"""
        # Given
        scraper_service.config['enable_images'] = True

        # When
        handler = scraper_service._create_route_handler()

        # Test tracker URL
        mock_route = AsyncMock()
        mock_route.request.url = "https://tracker.com/analytics.js"

        # Then: Tracker nên bị abort
        await handler(mock_route)
        mock_route.abort.assert_called_once()


# ==================== INTEGRATION TESTS ====================
@pytest.mark.integration
@pytest.mark.asyncio
class TestFacebookScraperServiceIntegration:
    """Integration tests - yêu cầu kết nối thực tế"""

    async def test_real_facebook_url(self, scraper_service):
        """Test với Facebook URL thực (chạy với browser)"""
        # Skip test này trên CI trừ khi có browser
        import os
        if os.getenv('CI') or os.getenv('GITHUB_ACTIONS'):
            pytest.skip("Skipping real browser test in CI")

        # Given - URL public Facebook post
        test_url = "https://www.facebook.com/facebook/posts/10158931489406729"

        try:
            # When
            await scraper_service.initialize()
            result = await scraper_service.scrape_single_url(test_url)

            # Then
            assert result is not None
            assert result['url'] == test_url

            if result['success']:
                assert 'title' in result
                assert 'page_info' in result
            else:
                # Có thể bị block, nhưng service nên xử lý được
                assert 'error' in result

        finally:
            await scraper_service.close()

    async def test_concurrent_scraping(self, scraper_service, sample_facebook_urls):
        """Test scraping đồng thời nhiều URLs"""
        # Skip trên CI
        import os
        if os.getenv('CI'):
            pytest.skip("Skipping concurrent test in CI")

        # Given
        urls = sample_facebook_urls * 2  # 8 URLs để test concurrency

        try:
            await scraper_service.initialize()

            # When - scrape đồng thời
            start_time = time.time()
            results = await scraper_service.scrape_multiple_urls(urls)
            total_time = time.time() - start_time

            # Then
            assert len(results) == len(urls)

            # Log performance
            print(f"\nConcurrent scraping: {len(urls)} URLs in {total_time:.2f}s")

        finally:
            await scraper_service.close()


# ==================== PERFORMANCE TESTS ====================
@pytest.mark.performance
class TestFacebookScraperServicePerformance:
    """Performance tests"""

    @pytest.mark.asyncio
    async def test_scrape_with_retry_performance(self, scraper_service):
        """Test hiệu năng với retry logic"""
        with patch.object(scraper_service, 'scrape_single_url') as mock_scrape:
            # Setup - fail 1 lần rồi success
            mock_scrape.side_effect = [
                Exception('First attempt fail'),
                {'url': 'test', 'success': True}
            ]

            # When
            start_time = time.time()
            result = await scraper_service.scrape_with_retry('test-url', max_retries=1)
            elapsed = time.time() - start_time

            # Then
            assert result['success'] == True
            # Có retry delay nên thời gian > 0
            assert elapsed > 0.5

    @pytest.mark.asyncio
    async def test_cache_performance(self, scraper_service):
        """Test hiệu năng cache"""
        import timeit

        # Given
        url = 'https://facebook.com/test-cache'
        cache_key = scraper_service._get_cache_key(url)
        scraper_service._cache[cache_key] = {
            'data': {'url': url, 'success': True},
            'timestamp': time.time()
        }

        # When - benchmark cache lookup
        def cache_lookup():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(scraper_service.scrape_single_url(url))
            loop.close()
            return result

        time_with_cache = timeit.timeit(cache_lookup, number=100)

        # Clear cache và test không có cache
        scraper_service._cache.clear()
        with patch.object(scraper_service, '_execute_scraping_algorithm') as mock_execute:
            mock_execute.return_value = {'url': url, 'success': True}

            def no_cache_lookup():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(scraper_service.scrape_single_url(url))
                loop.close()
                return result

            time_without_cache = timeit.timeit(no_cache_lookup, number=100)

        # Then - Cache nên nhanh hơn đáng kể
        print(f"\nCache performance: With cache: {time_with_cache:.4f}s, Without: {time_without_cache:.4f}s")
        assert time_with_cache < time_without_cache


# ==================== ERROR HANDLING TESTS ====================
@pytest.mark.asyncio
class TestFacebookScraperServiceErrorHandling:
    """Test xử lý lỗi”

    async def test_circuit_breaker_handling(self, scraper_service):
        """Test circuit breaker handling"""
        with patch.object(scraper_service.circuit_breaker, 'execute') as mock_execute:
            # Setup - circuit breaker mở
            mock_execute.side_effect = Exception('Circuit is open')

            # When
            result = await scraper_service.scrape_with_retry('test-url', max_retries=0)

            # Then
            assert result['success'] == False
            assert 'Circuit is open' in result['error']

    async def test_rate_limiter_handling(self, scraper_service):
        """Test rate limiter không block flow chính"""
        # Rate limiter nên được test riêng
        # Ở đây chỉ test integration
        with patch.object(scraper_service, '_execute_scraping_algorithm') as mock_execute:
            mock_execute.return_value = {'success': True}

            # Khi gọi nhiều lần, rate limiter không nên gây lỗi
            results = []
            for _ in range(10):
                result = await scraper_service.scrape_single_url('test-url')
                results.append(result)

            assert all(r['success'] for r in results)


# ==================== TEST RUNNER ====================
if __name__ == "__main__":
    """Cách chạy test thủ công"""

    # Chạy tất cả tests
    # pytest tests/test_facebook_scraper_service.py -v

    # Chạy tests với marker cụ thể
    # pytest tests/test_facebook_scraper_service.py -m "unit" -v
    # pytest tests/test_facebook_scraper_service.py -m "integration" -v
    # pytest tests/test_facebook_scraper_service.py -m "performance" -v

    # Chạy test với coverage
    # pytest tests/test_facebook_scraper_service.py --cov=app.services.facebook.facebook_scraper_service --cov-report=html

    # Chạy async tests
    # pytest tests/test_facebook_scraper_service.py::TestFacebookScraperServiceAsync -v

    print("Run tests with: pytest tests/test_facebook_scraper_service.py -v")