from enum import Enum
from typing import Optional, Dict, Any


class ErrorCode(str, Enum):
    # General errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    
    # Video-related errors
    INVALID_VIDEO_URL = "INVALID_VIDEO_URL"
    VIDEO_FETCH_FAILED = "VIDEO_FETCH_FAILED"
    VIDEO_PROCESSING_FAILED = "VIDEO_PROCESSING_FAILED"
    
    # Social integration errors
    INVALID_SOCIAL_URL = "INVALID_SOCIAL_URL"
    SOCIAL_FETCH_FAILED = "SOCIAL_FETCH_FAILED"
    SOCIAL_SCRAPING_FAILED = "SOCIAL_SCRAPING_FAILED"
    SOCIAL_RATE_LIMITED = "SOCIAL_RATE_LIMITED"
    
    # Authentication errors
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"


class AppException(Exception):
    """Base exception class for the application"""
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response"""
        result = {
            "code": self.code.value if isinstance(self.code, ErrorCode) else self.code,
            "message": self.message
        }
        if self.details:
            result["details"] = self.details
        return result