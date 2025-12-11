from fastapi import HTTPException
from app.services.youtube.youtube_download_service import YouTubeDownloadService
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class YouTubeDownloadController:

    @staticmethod
    async def download_video(url: str, quality: str):
        logger.info(f"Received request to download video: {url}, quality: {quality}")
        try:
            file_path = await YouTubeDownloadService.download_video(url, quality)
            logger.info(f"Video download completed successfully: {file_path}")
            return {"file_path": file_path}
        except Exception as e:
            logger.error(f"Error downloading video {url}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def download_audio(url: str, audio_format: str):
        logger.info(f"Received request to download audio: {url}, format: {audio_format}")
        try:
            file_path = await YouTubeDownloadService.download_audio(url, audio_format)
            logger.info(f"Audio download completed successfully: {file_path}")
            return {"file_path": file_path}
        except Exception as e:
            logger.error(f"Error downloading audio {url}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


