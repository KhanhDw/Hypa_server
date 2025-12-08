from pydantic import BaseModel

class YouTubeMetadata(BaseModel):
    video_id: str
    title: str | None
    description: str | None
    image: str | None
    url: str | None
    site_name: str | None = "YouTube"
    type: str | None = "video"
