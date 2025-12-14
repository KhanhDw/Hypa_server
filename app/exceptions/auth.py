from .base import AppException, ErrorCode


class UnauthorizedException(AppException):
    """Raised when user is not authorized to access a resource"""
    
    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            status_code=401
        )


class InvalidCredentialsException(AppException):
    """Raised when provided credentials are invalid"""
    
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(
            code=ErrorCode.INVALID_CREDENTIALS,
            message=message,
            status_code=401
        )


class TokenExpiredException(AppException):
    """Raised when authentication token has expired"""
    
    def __init__(self, message: str = "Token has expired"):
        super().__init__(
            code=ErrorCode.TOKEN_EXPIRED,
            message=message,
            status_code=401
        )


class InsufficientPermissionsException(AppException):
    """Raised when user doesn't have sufficient permissions"""
    
    def __init__(self, resource: str = "", action: str = ""):
        details = {}
        if resource:
            details["resource"] = resource
        if action:
            details["action"] = action
            
        super().__init__(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message=f"Insufficient permissions to {action} {resource}" if action and resource 
                    else "Insufficient permissions",
            status_code=403,
            details=details
        )