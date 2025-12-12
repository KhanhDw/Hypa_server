# controllers/facebook_controller.py
import time
import logging
import json
from typing import Dict, Any, List
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from ....models.facebook.facebook_metadata_model import ScrapeRequest, ScraperConfig
from ....services.facebook.product.scraper_core import AsyncFacebookScraperStreaming

logger = logging.getLogger(__name__)



def make_serializable(obj):
    """Hàm đệ quy để đảm bảo tất cả dữ liệu có thể serialize thành JSON"""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, dict):
        return {key: make_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(item) for item in obj]
    else:
        return str(obj)


class FacebookScraperController:
    def __init__(self):
        self.scraper = None
        self.config = None

    async def init_scraper(self, config: ScraperConfig):
        """Khởi tạo scraper với cấu hình"""
        # Nếu scraper đã tồn tại và cấu hình không thay đổi, không cần tạo mới
        if self.scraper and self.config == config:
            return self.scraper

        # Dọn dẹp scraper cũ nếu có
        if self.scraper:
            await self.cleanup()

        # Tạo scraper mới với cấu hình
        self.scraper = AsyncFacebookScraperStreaming(
            headless=config.headless,
            max_concurrent=config.max_concurrent,
            cache_ttl=config.cache_ttl,
            enable_images=config.enable_images,
            mode=config.mode  # Add mode parameter
        )
        # Khởi tạo context manager
        await self.scraper.__aenter__()
        self.config = config
        return self.scraper

    async def cleanup(self):
        """Dọn dẹp scraper"""
        if self.scraper:
            await self.scraper.__aexit__(None, None, None)
            self.scraper = None
            self.config = None

    # =============================================
    # PHƯƠNG PHÁP 1: Streaming Results
    # =============================================
    async def method_streaming(self, request: ScrapeRequest) -> Dict[str, Any]:
        """
        Phương pháp 1: Streaming - trả về kết quả ngay khi từng URL hoàn thành
        Tốt cho việc hiển thị progress real-time
        """
        start_time = time.time()

        try:
            # Khởi tạo scraper
            config = ScraperConfig(
                headless=request.headless,
                max_concurrent=request.max_concurrent,
                cache_ttl=request.cache_ttl,
                enable_images=request.enable_images,
                mode=request.mode  # Use mode from request if available
            )
            scraper = await self.init_scraper(config)

            # Chuẩn bị response
            response = {
                "method": "streaming",
                "success": True,
                "total_urls": len(request.urls),
                "mode": config.mode,  # Include mode in response
                "start_time": start_time,
                "results": [],
                "errors": []
            }

            # Xử lý streaming
            async for result in scraper.get_multiple_metadata_streaming(request.urls, mode=config.mode):
                url = result["url"]
                data = result["data"]

                # Thêm vào results
                serializable_data = make_serializable(data)
                response["results"].append({
                    "url": url,
                    "data": serializable_data,
                    "processed_at": time.time()
                })

                # Log errors
                if not data.get('success', False):
                    response["errors"].append({
                        "url": url,
                        "error": data.get('error', 'Unknown error')
                    })

            response["end_time"] = time.time()
            response["total_time"] = response["end_time"] - start_time
            response["successful_count"] = sum(1 for r in response["results"]
                                            if r["data"].get('success', False))
            response["failed_count"] = len(request.urls) - response["successful_count"]

            return response

        except Exception as e:
            logger.error(f"Error in method_streaming: {str(e)}")
            return {
                "method": "streaming",
                "success": False,
                "error": str(e),
                "start_time": start_time,
                "end_time": time.time(),
                "total_time": time.time() - start_time
            }

    # =============================================
    # PHƯƠNG PHÁP 2: Batch Processing
    # =============================================
    async def method_batch(self, request: ScrapeRequest) -> Dict[str, Any]:
        """
        Phương pháp 2: Batch - xử lý theo batch và trả về tất cả cùng lúc
        Tốt cho việc xử lý số lượng lớn URL
        """
        start_time = time.time()

        try:
            # Khởi tạo scraper
            config = ScraperConfig(
                headless=request.headless,
                max_concurrent=request.max_concurrent,
                cache_ttl=request.cache_ttl,
                enable_images=request.enable_images,
                mode=request.mode  # Use mode from request if available
            )
            scraper = await self.init_scraper(config)

            # Thực hiện batch scraping
            batch_size = request.batch_size or config.max_concurrent
            results = await scraper.get_multiple_metadata(request.urls, mode=config.mode, batch_size=batch_size)

            # Chuẩn bị response
            response = {
                "method": "batch",
                "success": True,
                "total_urls": len(request.urls),
                "batch_size": batch_size,
                "mode": config.mode,  # Include mode in response
                "start_time": start_time,
                "results": {},
                "summary": {},
                "errors": []
            }

            # Xử lý results
            successful_count = 0
            failed_count = 0

            for url, data in results.items():
                serializable_data = make_serializable(data)
                response["results"][url] = serializable_data

                if data.get('success', False):
                    successful_count += 1
                else:
                    failed_count += 1
                    response["errors"].append({
                        "url": url,
                        "error": data.get('error', 'Unknown error')
                    })

            response["end_time"] = time.time()
            response["total_time"] = response["end_time"] - start_time

            response["summary"] = {
                "successful": successful_count,
                "failed": failed_count,
                "cache_hits": sum(1 for data in results.values() if data.get('from_cache', False)),
                "cache_misses": sum(1 for data in results.values() if not data.get('from_cache', False)),
                "avg_scrape_time": sum(data.get('scrape_time', 0) for data in results.values()) / len(results) if results else 0
            }

            return response

        except Exception as e:
            logger.error(f"Error in method_batch: {str(e)}")
            return {
                "method": "batch",
                "success": False,
                "error": str(e),
                "start_time": start_time,
                "end_time": time.time(),
                "total_time": time.time() - start_time
            }

    # =============================================
    # PHƯƠNG PHÁP 3: Single URL
    # =============================================
    async def method_single(self, url: str, config: ScraperConfig) -> Dict[str, Any]:
        """Scrape một URL duy nhất"""
        start_time = time.time()

        try:
            scraper = await self.init_scraper(config)
            # Use the mode from config when calling get_facebook_metadata
            result = await scraper.get_facebook_metadata(url, mode=config.mode)

            response = {
                "method": "single",
                "success": True,
                "url": url,
                "mode": config.mode,  # Include mode in response
                "start_time": start_time,
                "end_time": time.time(),
                "total_time": time.time() - start_time,
                "data": make_serializable(result)
            }

            return response

        except Exception as e:
            logger.error(f"Error in method_single: {str(e)}")
            return {
                "method": "single",
                "success": False,
                "url": url,
                "mode": config.mode,  # Include mode in response
                "error": str(e),
                "start_time": start_time,
                "end_time": time.time(),
                "total_time": time.time() - start_time
            }