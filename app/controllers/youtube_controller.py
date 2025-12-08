from app.services.youtube.youtube_service_og import YouTubeServiceOg
from app.services.youtube.youtube_service_detail import YouTubeServiceDetail


class YouTubeController:
# --- OG ---

    @staticmethod
    async def get_metadata_og(url: str):
        return await YouTubeServiceOg.fetch_metadata(url)

# --- DETAIL ---

    @staticmethod
    async def get_metadata_detail(url: str):
        return await YouTubeServiceDetail.fetch_metadata(url)


