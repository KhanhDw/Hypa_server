from fastapi import APIRouter
from . import root_routes, user_routes, auth_routes
from .platforms import router as metadata_routes

router = APIRouter()

router.include_router(root_routes.router, tags=["root"])
router.include_router(metadata_routes, prefix="/metadata", tags=["metadata"])
router.include_router(user_routes.router, prefix="/users", tags=["users"])
router.include_router(auth_routes.router, prefix="/auth", tags=["authentication"])

__all__ = ["router"]