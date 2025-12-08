import os
import re
import asyncio
import yt_dlp
from pathlib import Path
from app.services.ffmpeg_service.ffmpeg_service import ffmpeg_service
from app.services.youtube.youtube_config import YouTubeConfig

class YouTubeDownloadService:
    # --- FFmpeg Portable ---
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FFMPEG_DIR = os.path.join(BASE_DIR,"..","..","..", "ffmpeg", "bin")  # thư mục có ffmpeg.exe

    # --- Fix lỗi filename Windows ---
    @staticmethod
    def safe_filename(name: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", name)

    # ============================================================
    # DOWNLOAD VIDEO PUBLIC API
    # ============================================================
    @staticmethod
    async def download_video(url: str, quality: str = "720p", mode: str = "merged") -> str:
        """
        mode:
            - "video":   chỉ video, không audio
            - "merged":  video + audio (có âm thanh)
        """
        return await asyncio.get_event_loop().run_in_executor(
            None,
            YouTubeDownloadService._download_video_sync,
            url, quality, mode
        )

    # --- WORKER ---
    @staticmethod
    def _download_video_sync(url: str, quality: str, mode: str) -> str:
        Path("downloads").mkdir(exist_ok=True)

        # Lấy tên file an toàn
        safe_title = YouTubeDownloadService.safe_filename(url.split("v=")[-1])  # tạm lấy ID

        if mode == "video":
            # 🎯 Chỉ video
            opts = YouTubeConfig.get_video_options(quality)
            opts["outtmpl"] = f"downloads/{safe_title}_video_only.%(ext)s"
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            video_path = f"downloads/{safe_title}_video_only.{info.get('ext','mp4')}"
            return video_path

        elif mode == "merged":
            # 1️⃣ Download video-only
            opts_video = YouTubeConfig.get_merged_video_options(quality)
            opts_video["outtmpl"] = f"downloads/{safe_title}_video.%(ext)s"
            with yt_dlp.YoutubeDL(opts_video) as ydl:
                info_video = ydl.extract_info(url, download=True)
            video_path = f"downloads/{safe_title}_video.{info_video.get('ext','mp4')}"

            # 2️⃣ Download audio-only
            opts_audio = YouTubeConfig.get_audio_options()
            opts_audio["outtmpl"] = f"downloads/{safe_title}_audio.%(ext)s"
            with yt_dlp.YoutubeDL(opts_audio) as ydl:
                info_audio = ydl.extract_info(url, download=True)
            audio_ext = info_audio.get("ext", "m4a")
            audio_path = f"downloads/{safe_title}_audio.{audio_ext}"

            # 3️⃣ Merge bằng FFmpegService
            merged_path = f"downloads/{safe_title}_merged.mp4"

            # Run FFmpeg merge command with proper error handling
            stdout, stderr = ffmpeg_service.run([
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-strict", "experimental",
                "-y",  # overwrite output file if exists
                merged_path
            ])

            # Check if merge was successful by verifying the output file exists
            if os.path.exists(merged_path):
                # Clean up temporary files
                try:
                    os.remove(video_path)
                    os.remove(audio_path)
                except OSError:
                    pass  # Ignore errors when removing temporary files
                return merged_path
            else:
                # If merge failed, return one of the downloaded files as fallback and show error
                print(f"FFmpeg merge failed. Stderr: {stderr}")
                raise Exception(f"FFmpeg merge failed: {stderr}")

        else:
            raise ValueError("Invalid mode. Choose 'video' or 'merged'.")


    # ============================================================
    # DOWNLOAD AUDIO MP3
    # ============================================================
    @staticmethod
    async def download_audio(url: str, audio_format: str = "mp3") -> str:
        return await asyncio.get_event_loop().run_in_executor(
            None,
            YouTubeDownloadService._download_audio_sync,
            url, audio_format
        )

    @staticmethod
    def _download_audio_sync(url: str, audio_format: str) -> str:
        Path("downloads").mkdir(exist_ok=True)

        opts = YouTubeConfig.get_audio_extraction_options(audio_format)
        opts["ffmpeg_location"] = YouTubeDownloadService.FFMPEG_DIR

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        safe_title = YouTubeDownloadService.safe_filename(info["title"])
        return f"downloads/{safe_title}.{audio_format}"
