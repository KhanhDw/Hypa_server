import yt_dlp
from pathlib import Path
from app.models.metadata_model import YouTubeMetadata
from app.services.youtube.youtube_config import YouTubeConfig
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class YouTubeServiceDetail:

    @staticmethod
    async def fetch_metadata(url: str) -> YouTubeMetadata:
        logger.info(f"Fetching detailed metadata for URL: {url}")
        try:
            opts = YouTubeConfig.get_metadata_options()

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            result = YouTubeMetadata(
                video_id=info.get("id"),
                title=info.get("title"),
                description=info.get("description"),  # FULL DESCRIPTION
                image=info.get("thumbnail"),
                url=info.get("webpage_url"),
            )
            logger.info(f"Successfully fetched detailed metadata for video ID: {info.get('id', 'unknown')}")
            return result
        except Exception as e:
            logger.error(f"Error fetching detailed metadata for {url}: {str(e)}")
            raise