from fastapi import APIRouter, Query
from app.controllers.youtube_controller import YouTubeController

router = APIRouter()

@router.get("/")
async def get_metadata_og(url: str = Query(...)):
    return await YouTubeController.get_metadata_og(url)
