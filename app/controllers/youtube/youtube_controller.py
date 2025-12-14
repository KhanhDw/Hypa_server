from app.services.youtube.youtube_service_og import YouTubeServiceOg
from app.services.youtube.youtube_service_detail import YouTubeServiceDetail
from app.config.logging_config import get_logger

logger = get_logger(__name__)


class YouTubeController:
# --- OG ---

    @staticmethod
    async def get_metadata_og(url: str):
        logger.info(f"Received request to fetch OG metadata: {url}")
        result = await YouTubeServiceOg.fetch_metadata(url)
        logger.info(f"OG metadata fetched successfully for: {url}")
        return result

# --- DETAIL ---

    @staticmethod
    async def get_metadata_detail(url: str):
        logger.info(f"Received request to fetch detailed metadata: {url}")
        result = await YouTubeServiceDetail.fetch_metadata(url)
        logger.info(f"Detailed metadata fetched successfully for: {url}")
        return result


