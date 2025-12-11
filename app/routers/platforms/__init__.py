from .youtube import router as youtube_router
from .facebook import router as facebook_router

# Create a main router that includes both YouTube and Facebook routers
from fastapi import APIRouter
router = APIRouter()
router.include_router(youtube_router, prefix="/youtube", tags=["youtube"])
router.include_router(facebook_router, prefix="/facebook", tags=["facebook"])

__all__ = ["router"]