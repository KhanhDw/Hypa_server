from .base import AppException, ErrorCode


class InvalidVideoURLException(AppException):
    """Raised when the video URL is not valid"""
    
    def __init__(self, url: str = ""):
        super().__init__(
            code=ErrorCode.INVALID_VIDEO_URL,
            message=f"Invalid video URL: {url}" if url else "Invalid video URL provided",
            status_code=400
        )


class VideoFetchFailedException(AppException):
    """Raised when fetching video metadata or content fails"""
    
    def __init__(self, url: str = "", reason: str = ""):
        details = {"url": url}
        if reason:
            details["reason"] = reason
            
        super().__init__(
            code=ErrorCode.VIDEO_FETCH_FAILED,
            message=f"Failed to fetch video: {url}" if url else "Failed to fetch video",
            status_code=500,
            details=details
        )


class VideoProcessingFailedException(AppException):
    """Raised when video processing fails"""
    
    def __init__(self, url: str = "", reason: str = ""):
        details = {"url": url}
        if reason:
            details["reason"] = reason
            
        super().__init__(
            code=ErrorCode.VIDEO_PROCESSING_FAILED,
            message=f"Failed to process video: {url}" if url else "Failed to process video",
            status_code=500,
            details=details
        )