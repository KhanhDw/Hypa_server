# routers/facebook_router.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ....models.facebook.facebook_metadata_model import ScrapeRequest, ScraperConfig
from ....controllers.facebook.product.facebook_controller import FacebookScraperController

# Tạo router với prefix
router = APIRouter(prefix="/facebook", tags=["facebook"])

# Khởi tạo controller
controller = FacebookScraperController()


@router.get("/")
async def facebook_root():
    """Trang chủ cho Facebook scraper"""
    return {
        "message": "Facebook Scraper API",
        "endpoints": {
            "/streaming": "Scrape URLs with streaming method (POST)",
            "/batch": "Scrape URLs with batch method (POST)",
            "/single": "Scrape single URL (GET)",
            "/config": "Update scraper configuration (POST)"
        }
    }


@router.post("/streaming")
async def scrape_streaming(request: ScrapeRequest):
    """
    Phương pháp Streaming:
    - Trả về kết quả ngay khi từng URL hoàn thành
    - Tốt cho real-time progress
    """
    try:
        print("Received streaming request:-->>>>", request)
        result = await controller.method_streaming(request)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def scrape_batch(request: ScrapeRequest):
    """
    Phương pháp Batch:
    - Xử lý theo batch và trả về tất cả cùng lúc
    - Tốt cho xử lý số lượng lớn
    """
    try:
        result = await controller.method_batch(request)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/single")
async def scrape_single(
    url: str,
    headless: bool = True,
    max_concurrent: int = 5,
    cache_ttl: int = 600,
    enable_images: bool = True
):
    """
    Scrape một URL duy nhất
    """
    try:
        config = ScraperConfig(
            headless=headless,
            max_concurrent=max_concurrent,
            cache_ttl=cache_ttl,
            enable_images=enable_images
        )
        result = await controller.method_single(url, config)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_config(config: ScraperConfig):
    """
    Cập nhật cấu hình scraper
    """
    try:
        # Cleanup scraper cũ nếu có
        await controller.cleanup()

        # Khởi tạo scraper mới
        await controller.init_scraper(config)

        return {
            "success": True,
            "message": "Configuration updated",
            "config": config.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check cho Facebook scraper"""
    return {
        "status": "healthy",
        "scraper_initialized": controller.scraper is not None
    }