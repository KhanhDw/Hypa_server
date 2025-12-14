import httpx
import trafilatura
import re
from app.utils.youtube_parser import extract_youtube_id
from app.models.youtube.youtube_metadata_model import YouTubeMetadata
from app.config.logging_config import get_logger
from app.exceptions.video import InvalidVideoURLException, VideoFetchFailedException

logger = get_logger(__name__)


class YouTubeServiceOg:

    @staticmethod
    async def fetch_metadata(url: str) -> YouTubeMetadata:
        logger.info(f"Fetching OG metadata for URL: {url}")
        video_id = extract_youtube_id(url)
        if not video_id:
            raise InvalidVideoURLException(url)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64"
                ") AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/120.0.0.0 Safari/537.36"
            )
        }

        # ---- Fetch HTML ----
        try:
            async with httpx.AsyncClient(timeout=10, headers=headers) as client:
                res = await client.get(url)
                html = res.text
                logger.info(f"Successfully fetched HTML for video ID: {video_id}")
        except Exception as e:
            logger.error(f"Error fetching HTML for {url}: {str(e)}")
            raise VideoFetchFailedException(url, str(e))

        # ---- Parse metadata ----
        try:
            metadata = trafilatura.metadata.extract_metadata(html)
            logger.debug(f"Successfully extracted metadata for video ID: {video_id}")
        except Exception as e:
            logger.warning(f"Error extracting metadata with trafilatura for {video_id}: {str(e)}")
            metadata = None

        title = None
        description = None
        og_image = None
        og_url = None

        if metadata:
            title = getattr(metadata, "title", None)
            description = getattr(metadata, "description", None)
            og_url = getattr(metadata, "url", None)

        # ---- Fallback OG parser ----
        def find_og(prop):
            pattern = rf'<meta[^>]+property="{prop}"[^>]+content="([^"]+)"'
            match = re.search(pattern, html)
            return match.group(1) if match else None

        title = title or find_og("og:title")
        description = description or find_og("og:description")
        og_image = find_og("og:image")
        og_url = og_url or find_og("og:url") or url

        image = og_image or f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

        result = YouTubeMetadata(
            video_id=video_id,
            title=title,
            description=description,
            image=image,
            url=og_url,
        )
        logger.info(f"Successfully fetched OG metadata for video ID: {video_id}")
        return result