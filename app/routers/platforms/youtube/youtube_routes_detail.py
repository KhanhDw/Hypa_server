from fastapi import APIRouter, Query
from app.controllers.youtube_controller import YouTubeController
from app.controllers.youtube_download_controller import YouTubeDownloadController
from app.config.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.get("/")
async def get_metadata_detail(url: str = Query(...)):
    logger.info(f"Received request for detailed metadata: {url}")
    try:
        result = await YouTubeController.get_metadata_detail(url)
        logger.info(f"Successfully returned detailed metadata for: {url}")
        return result
    except Exception as e:
        logger.error(f"Error in detailed metadata request for {url}: {str(e)}")
        raise

@router.get("/download-video")
async def download_video(
    url: str = Query(...),
    quality: str = Query("720p", description="Quality: 360p, 480p, 720p, 1080p"),
    mode: str = Query("merged", description="Mode: video, merged")
):
    logger.info(f"Received request to download video: {url}, quality: {quality}, mode: {mode}")
    try:
        result = await YouTubeDownloadController.download_video(url, quality)
        logger.info(f"Successfully returned download video response for: {url}")
        return result
    except Exception as e:
        logger.error(f"Error in download video request for {url}: {str(e)}")
        raise


@router.get("/download-audio")
async def download_audio(
    url: str = Query(...),
    audio_format: str = Query("mp3", description="Format: mp3, m4a, webm")
):
    logger.info(f"Received request to download audio: {url}, format: {audio_format}")
    try:
        result = await YouTubeDownloadController.download_audio(url, audio_format)
        logger.info(f"Successfully returned download audio response for: {url}")
        return result
    except Exception as e:
        logger.error(f"Error in download audio request for {url}: {str(e)}")
        raise