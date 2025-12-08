from fastapi import APIRouter, Query
from app.controllers.youtube_controller import YouTubeController
from app.controllers.youtube_download_controller import YouTubeDownloadController


router = APIRouter()

@router.get("/")
async def get_metadata_detail(url: str = Query(...)):
    return await YouTubeController.get_metadata_detail(url)

@router.get("/download-video")
async def download_video(
    url: str = Query(...),
    quality: str = Query("720p", description="Quality: 360p, 480p, 720p, 1080p"),
    mode: str = Query("merged", description="Mode: video, merged")
):
    return await YouTubeDownloadController.download_video(url, quality)


@router.get("/download-audio")
async def download_audio(
    url: str = Query(...),
    audio_format: str = Query("mp3", description="Format: mp3, m4a, webm")
):
    return await YouTubeDownloadController.download_audio(url, audio_format)