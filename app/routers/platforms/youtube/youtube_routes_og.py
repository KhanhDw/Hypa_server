from fastapi import APIRouter, Query
from app.controllers.youtube.youtube_controller import YouTubeController
from app.config.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.get("")
async def get_metadata_og(url: str = Query(...)):
    logger.info(f"Received request for OG metadata: {url}")
    try:
        result = await YouTubeController.get_metadata_og(url)
        logger.info(f"Successfully returned OG metadata for: {url}")
        return result
    except Exception as e:
        logger.error(f"Error in OG metadata request for {url}: {str(e)}")
        raise
