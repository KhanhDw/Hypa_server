# routers/facebook_router.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import time

from ....models.facebook.facebook_metadata_model import ScrapeRequest, ScraperConfig
from ....controllers.facebook.product.facebook_controller import FacebookScraperController
from ....services.facebook.product.scaler import scaler

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


# Scaling-related endpoints
@router.get("/scaling/status")
async def get_scaling_status():
    """Get current scaling status including worker count, queue lengths, and memory usage"""
    try:
        scaling_status = scaler.get_current_status()
        return JSONResponse(content={
            "status": "success",
            "data": scaling_status
        }, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting scaling status: {str(e)}")


@router.post("/scaling/manual")
async def manual_scaling_operation(operation: str, value: int = None):
    """
    Manual scaling operations
    Operations: 'scale_up', 'scale_down', 'set_workers'
    """
    try:
        if operation == "scale_up":
            # Increase worker count manually
            if scaler.current_workers < scaler.max_workers:
                scaler.current_workers += 1
                scaler.last_scaling_action = time.time()
                scaler.scaling_history.append({
                    'timestamp': time.time(),
                    'action': 'manual_scale_up',
                    'from_workers': scaler.current_workers - 1,
                    'to_workers': scaler.current_workers,
                    'reason': 'manual_operation'
                })
                return {"status": "success", "message": f"Workers scaled up to {scaler.current_workers}"}
            else:
                return {"status": "warning", "message": f"Already at max workers ({scaler.max_workers})"}
                
        elif operation == "scale_down":
            # Decrease worker count manually
            if scaler.current_workers > scaler.min_workers:
                scaler.current_workers -= 1
                scaler.last_scaling_action = time.time()
                scaler.scaling_history.append({
                    'timestamp': time.time(),
                    'action': 'manual_scale_down',
                    'from_workers': scaler.current_workers + 1,
                    'to_workers': scaler.current_workers,
                    'reason': 'manual_operation'
                })
                return {"status": "success", "message": f"Workers scaled down to {scaler.current_workers}"}
            else:
                return {"status": "warning", "message": f"Already at min workers ({scaler.min_workers})"}
                
        elif operation == "set_workers":
            if value is not None:
                if scaler.min_workers <= value <= scaler.max_workers:
                    old_workers = scaler.current_workers
                    scaler.current_workers = value
                    scaler.last_scaling_action = time.time()
                    scaler.scaling_history.append({
                        'timestamp': time.time(),
                        'action': 'manual_set_workers',
                        'from_workers': old_workers,
                        'to_workers': scaler.current_workers,
                        'reason': 'manual_operation'
                    })
                    return {"status": "success", "message": f"Workers set to {scaler.current_workers}"}
                else:
                    return {"status": "error", "message": f"Value must be between {scaler.min_workers} and {scaler.max_workers}"}
            else:
                return {"status": "error", "message": "Value parameter required for set_workers operation"}
        else:
            return {"status": "error", "message": "Invalid operation. Use 'scale_up', 'scale_down', or 'set_workers'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during scaling operation: {str(e)}")


@router.post("/scaling/restart-workers")
async def restart_workers_if_needed():
    """Manually trigger worker restart if memory usage is high"""
    try:
        workers_to_restart = scaler.get_workers_to_restart()
        restart_performed = scaler.restart_workers_if_needed()
        return JSONResponse(content={
            "status": "success",
            "restart_performed": restart_performed,
            "workers_to_restart": workers_to_restart,
            "message": f"Checked for worker restart. Restart performed: {restart_performed}"
        }, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restarting workers: {str(e)}")