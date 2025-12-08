import os
import re
import asyncio
import yt_dlp
from pathlib import Path
from app.services.ffmpeg_service.ffmpeg_service import ffmpeg_service
from app.services.youtube.youtube_config import YouTubeConfig
from app.config.logging_config import get_logger
import datetime

logger = get_logger(__name__)

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
        logger.info(f"Starting video download: {url}, quality: {quality}, mode: {mode}")
        Path("downloads").mkdir(exist_ok=True)

        # =========================================================
        # 1. TRÍCH XUẤT THÔNG TIN VIDEO ĐỂ LẤY TÊN (TITLE)
        # =========================================================
        try:
            temp_opts = {"quiet": True}  # Dùng tùy chọn cơ bản để lấy info
            with yt_dlp.YoutubeDL(temp_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"Failed to extract info for {url}: {str(e)}")
            # Trả về lỗi nếu không lấy được thông tin
            raise ValueError(f"Could not get video information for {url}") from e

        datetime_opts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        # Lấy tên file an toàn
        safe_title = datetime_opts +"_"+ YouTubeDownloadService.safe_filename(info.get("title", url.split("v=")[-1]))

        if mode == "video":
            # 🎯 Chỉ video
            logger.info(f"Downloading video only for: {url}")
            opts = YouTubeConfig.get_video_options(quality)
            opts["outtmpl"] = f"downloads/{safe_title}_video_only.%(ext)s"
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            video_path = f"downloads/{safe_title}_video_only.{info.get('ext','mp4')}"
            logger.info(f"Video download completed: {video_path}")
            return video_path

        elif mode == "merged":
            # Download a merged video file (video + audio combined)
            logger.info(f"Downloading merged video for: {url}")
            opts = YouTubeConfig.get_merged_video_options(quality)
            opts["outtmpl"] = f"downloads/{safe_title}_FULL.%(ext)s"
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            merged_path = f"downloads/{safe_title}_FULL.{info.get('ext','mp4')}"
            logger.info(f"Merged video download completed: {merged_path}")
            return merged_path

        else:
            error_msg = "Invalid mode. Choose 'video' or 'merged'."
            logger.error(error_msg)
            raise ValueError(error_msg)


    # ============================================================
    # DOWNLOAD AUDIO MP3
    # ============================================================
    @staticmethod
    async def download_audio(url: str, audio_format: str = "mp3") -> str:
        logger.info(f"Received request to download audio: {url}, format: {audio_format}")
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                YouTubeDownloadService._download_audio_sync,
                url, audio_format
            )
            logger.info(f"Audio download completed successfully: {result}")
            return result
        except Exception as e:
            logger.error(f"Error in async audio download for {url}: {str(e)}")
            raise

    @staticmethod
    def _download_audio_sync(url: str, audio_format: str) -> str:
        logger.info(f"Starting audio download: {url}, format: {audio_format}")
        Path("downloads").mkdir(exist_ok=True)

        # First extract video info to get the title
        try:
            temp_opts = {"quiet": True}  # Dùng tùy chọn cơ bản để lấy info
            with yt_dlp.YoutubeDL(temp_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"Failed to extract info for {url}: {str(e)}")
            raise ValueError(f"Could not get video information for {url}") from e

        datetime_opts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        # Create a safe title with timestamp
        safe_title = datetime_opts + "_" + YouTubeDownloadService.safe_filename(info.get("title", url.split("v=")[-1]))

        # Try audio-only download first
        opts = YouTubeConfig.get_audio_extraction_options(audio_format)
        opts["outtmpl"] = f"downloads/{safe_title}.%(ext)s"
        opts["ffmpeg_location"] = YouTubeDownloadService.FFMPEG_DIR

        try:
            logger.info(f"Attempting audio-only download for {url}")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                logger.debug(f"Audio-only download info: {info.get('title', 'Unknown')} - {info.get('id', 'Unknown ID')}")
        except Exception as e:
            logger.warning(f"Audio-only download failed for {url}, attempting fallback: {str(e)}")
            # Fallback: download lowest quality video and extract audio
            return YouTubeDownloadService._download_audio_from_lowest_quality_video(url, audio_format, safe_title)

        # The file should be created with the expected name
        expected_audio_path = f"downloads/{safe_title}.{audio_format}"

        # Check if the expected file exists
        if Path(expected_audio_path).exists():
            audio_path = expected_audio_path
        else:
            # If not found, find the most recently created file with the correct extension
            audio_files = [f for f in Path("downloads").iterdir() if f.suffix[1:] == audio_format]
            if audio_files:
                # Get the most recently created file
                audio_path = str(max(audio_files, key=lambda f: f.stat().st_mtime))
            else:
                raise FileNotFoundError(f"Audio file not found after download: {expected_audio_path}")

        logger.info(f"Audio download completed: {audio_path}")
        return audio_path

    @staticmethod
    def _download_audio_from_lowest_quality_video(url: str, audio_format: str, safe_title: str) -> str:
        """
        Fallback method: Download lowest quality video and extract audio from it
        """
        logger.info(f"Using fallback: downloading lowest quality video to extract audio from {url}")

        # Get options for lowest quality video download
        opts = YouTubeConfig.get_lowest_quality_video_options()
        temp_video_path = f"downloads/{safe_title}_temp_video.%(ext)s"
        opts["outtmpl"] = temp_video_path
        opts["ffmpeg_location"] = YouTubeDownloadService.FFMPEG_DIR

        # Download the lowest quality video
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Find the downloaded video file
        temp_video_files = list(Path("downloads").glob(f"{safe_title}_temp_video.*"))
        if not temp_video_files:
            raise FileNotFoundError(f"Lowest quality video file not found after download for {url}")

        temp_video_file = str(temp_video_files[0])
        logger.info(f"Downloaded lowest quality video: {temp_video_file}")

        # Now extract audio from the downloaded video using FFmpeg
        output_audio_path = f"downloads/{safe_title}.{audio_format}"
        try:
            from app.services.ffmpeg_service.ffmpeg_service import ffmpeg_service
            # Extract audio using FFmpeg with appropriate codec based on format
            if audio_format.lower() == "mp3":
                cmd_args = ["-i", temp_video_file, "-vn", "-acodec", "mp3", "-ab", "320k", "-y", output_audio_path]
            elif audio_format.lower() == "m4a":
                cmd_args = ["-i", temp_video_file, "-vn", "-acodec", "aac", "-ab", "320k", "-y", output_audio_path]
            elif audio_format.lower() == "aac":
                cmd_args = ["-i", temp_video_file, "-vn", "-acodec", "aac", "-ab", "320k", "-y", output_audio_path]
            elif audio_format.lower() == "flac":
                cmd_args = ["-i", temp_video_file, "-vn", "-acodec", "flac", "-y", output_audio_path]
            elif audio_format.lower() == "opus":
                cmd_args = ["-i", temp_video_file, "-vn", "-acodec", "libopus", "-ab", "320k", "-y", output_audio_path]
            elif audio_format.lower() == "wav":
                cmd_args = ["-i", temp_video_file, "-vn", "-acodec", "pcm_s16le", "-y", output_audio_path]
            else:
                # Default to MP3 if format is not recognized
                cmd_args = ["-i", temp_video_file, "-vn", "-acodec", "mp3", "-ab", "320k", "-y", output_audio_path]
            
            ffmpeg_service.run_with_check(cmd_args)
            logger.info(f"Successfully extracted audio from video: {output_audio_path}")
        except Exception as e:
            logger.error(f"Failed to extract audio using FFmpeg: {str(e)}")
            # Fallback: try using yt-dlp's audio extraction on the downloaded video
            try:
                extract_opts = YouTubeConfig.get_audio_extraction_options(audio_format)
                extract_opts["format"] = "bestaudio/best"  # Use best available audio from the video
                extract_opts["outtmpl"] = output_audio_path
                extract_opts["ffmpeg_location"] = YouTubeDownloadService.FFMPEG_DIR

                with yt_dlp.YoutubeDL(extract_opts) as ydl:
                    ydl.download([f"file://{temp_video_file}"])  # Download from local file

                logger.info(f"Successfully extracted audio using yt-dlp fallback: {output_audio_path}")
            except Exception as fallback_e:
                logger.error(f"Both FFmpeg and yt-dlp fallbacks failed: {str(fallback_e)}")
                raise

        # Clean up the temporary video file
        try:
            Path(temp_video_file).unlink()
            logger.debug(f"Cleaned up temporary video file: {temp_video_file}")
        except Exception as e:
            logger.warning(f"Could not clean up temporary video file {temp_video_file}: {str(e)}")

        return output_audio_path
