from fastapi import APIRouter
from . import youtube_routes_og
from . import youtube_routes_detail

router = APIRouter()

router.include_router(youtube_routes_og.router, prefix="/youtube-og", tags=["youtube-og"])
router.include_router(youtube_routes_detail.router, prefix="/youtube-detail", tags=["youtube-detail"])

__all__ = ["router"]