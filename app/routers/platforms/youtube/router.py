from fastapi import APIRouter
from . import youtube_routes_og
from . import youtube_routes_full

router = APIRouter()

router.include_router(youtube_routes_og.router, prefix="/og", tags=["youtube-og"])
router.include_router(youtube_routes_full.router, prefix="/full", tags=["youtube-full"])

__all__ = ["router"]