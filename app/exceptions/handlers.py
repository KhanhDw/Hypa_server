from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from typing import Union
import logging

from .base import AppException
from .video import *
from .social_integration import *
from .auth import *

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle AppException and return consistent error response"""
    logger.error(f"AppException: {exc.code.value} - {exc.message}", exc_info=True)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors"""
    logger.warning(f"Validation error: {exc}")
    
    return JSONResponse(
        status_code=400,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Validation failed",
            "details": {
                "errors": [
                    {
                        "field": err.get("loc", ["unknown"])[-1],
                        "message": err.get("msg", "Invalid value"),
                        "type": err.get("type", "validation_error")
                    }
                    for err in exc.errors()
                ]
            }
        }
    )


# Only register SQLAlchemy handler if SQLAlchemy is available
try:
    from sqlalchemy.exc import SQLAlchemyError
    
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        """Handle SQLAlchemy database errors"""
        logger.error(f"Database error: {exc}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Database error occurred"
            }
        )
        
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions (fallback)"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Something went wrong"
        }
    )