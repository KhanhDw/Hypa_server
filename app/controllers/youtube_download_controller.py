from fastapi import HTTPException
from app.services.youtube.youtube_download_service import YouTubeDownloadService

class YouTubeDownloadController:

    @staticmethod
    async def download_video(url: str, quality: str):
        try:
            file_path = await YouTubeDownloadService.download_video(url, quality)
            return {"file_path": file_path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def download_audio(url: str, audio_format: str):
        try:
            file_path = await YouTubeDownloadService.download_audio(url, audio_format)
            return {"file_path": file_path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


