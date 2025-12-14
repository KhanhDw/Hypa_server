from .base import AppException, ErrorCode


class InvalidSocialURLException(AppException):
    """Raised when the social media URL is not valid"""
    
    def __init__(self, url: str = "", platform: str = ""):
        details = {"url": url}
        if platform:
            details["platform"] = platform
            
        super().__init__(
            code=ErrorCode.INVALID_SOCIAL_URL,
            message=f"Invalid {platform} URL: {url}" if platform and url else "Invalid social media URL provided",
            status_code=400,
            details=details
        )


class SocialFetchFailedException(AppException):
    """Raised when fetching social media content fails"""
    
    def __init__(self, url: str = "", platform: str = "", reason: str = ""):
        details = {"url": url, "platform": platform}
        if reason:
            details["reason"] = reason
            
        super().__init__(
            code=ErrorCode.SOCIAL_FETCH_FAILED,
            message=f"Failed to fetch {platform} content: {url}" if platform and url else "Failed to fetch social media content",
            status_code=500,
            details=details
        )


class SocialScrapingFailedException(AppException):
    """Raised when scraping social media content fails"""
    
    def __init__(self, url: str = "", platform: str = "", reason: str = ""):
        details = {"url": url, "platform": platform}
        if reason:
            details["reason"] = reason
            
        super().__init__(
            code=ErrorCode.SOCIAL_SCRAPING_FAILED,
            message=f"Failed to scrape {platform} content: {url}" if platform and url else "Failed to scrape social media content",
            status_code=500,
            details=details
        )


class SocialRateLimitedException(AppException):
    """Raised when social media API rate limit is exceeded"""
    
    def __init__(self, platform: str = "", reset_time: str = ""):
        details = {"platform": platform}
        if reset_time:
            details["reset_time"] = reset_time
            
        super().__init__(
            code=ErrorCode.SOCIAL_RATE_LIMITED,
            message=f"Rate limit exceeded for {platform}" if platform else "Social media API rate limit exceeded",
            status_code=429,
            details=details
        )