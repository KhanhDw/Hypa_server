import yt_dlp
from pathlib import Path
from app.models.metadata_model import YouTubeMetadata
from app.services.youtube.youtube_config import YouTubeConfig

class YouTubeServiceDetail:

    @staticmethod
    async def fetch_metadata(url: str) -> YouTubeMetadata:
        opts = YouTubeConfig.get_metadata_options()

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return YouTubeMetadata(
            video_id=info.get("id"),
            title=info.get("title"),
            description=info.get("description"),  # FULL DESCRIPTION
            image=info.get("thumbnail"),
            url=info.get("webpage_url"),
        )