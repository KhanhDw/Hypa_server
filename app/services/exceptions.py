"""Custom exception hierarchy for the service layer"""

class ServiceError(Exception):
    """Base exception for all service-related errors"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ValidationError(ServiceError):
    """Raised when input validation fails"""
    def __init__(self, message: str = "Invalid input provided"):
        super().__init__(message, "VALIDATION_ERROR")


class URLValidationError(ValidationError):
    """Raised when URL validation fails"""
    def __init__(self, message: str = "Invalid or unsafe URL provided"):
        super().__init__(message)


class FetchError(ServiceError):
    """Raised when fetching content from URL fails"""
    def __init__(self, message: str = "Failed to fetch content from URL"):
        super().__init__(message, "FETCH_ERROR")


class HTTPFetchError(FetchError):
    """Raised when HTTP request to fetch content fails"""
    def __init__(self, status_code: int, message: str = None):
        if message is None:
            message = f"HTTP request failed with status code {status_code}"
        super().__init__(message)
        self.status_code = status_code


class ContentError(ServiceError):
    """Raised when content processing fails"""
    def __init__(self, message: str = "Error processing content"):
        super().__init__(message, "CONTENT_ERROR")


class UnsupportedContentTypeError(ContentError):
    """Raised when content type is not supported"""
    def __init__(self, content_type: str):
        message = f"Content type '{content_type}' is not supported"
        super().__init__(message)
        self.content_type = content_type


class ParseError(ServiceError):
    """Raised when content parsing fails"""
    def __init__(self, message: str = "Error parsing content"):
        super().__init__(message, "PARSE_ERROR")


class ServiceTimeoutError(ServiceError):
    """Raised when a service operation times out"""
    def __init__(self, message: str = "Operation timed out"):
        super().__init__(message, "TIMEOUT_ERROR")


class CacheError(ServiceError):
    """Raised when cache operations fail"""
    def __init__(self, message: str = "Cache operation failed"):
        super().__init__(message, "CACHE_ERROR")