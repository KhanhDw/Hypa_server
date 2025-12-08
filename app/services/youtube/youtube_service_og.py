import httpx
import trafilatura
import re
from app.utils.youtube_parser import extract_youtube_id
from app.models.metadata_model import YouTubeMetadata


class YouTubeServiceOg:

    @staticmethod
    async def fetch_metadata(url: str) -> YouTubeMetadata:
        video_id = extract_youtube_id(url)
        if not video_id:
            raise ValueError("URL không phải là YouTube hợp lệ")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64"
                ") AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/120.0.0.0 Safari/537.36"
            )
        }

        # ---- Fetch HTML ----
        async with httpx.AsyncClient(timeout=10, headers=headers) as client:
            res = await client.get(url)
            html = res.text

        # ---- Parse metadata ----
        metadata = trafilatura.metadata.extract_metadata(html)

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

        return YouTubeMetadata(
            video_id=video_id,
            title=title,
            description=description,
            image=image,
            url=og_url,
        )
