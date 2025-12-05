from pydantic_settings import SettingsConfigDict, BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Server settings
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_reload: bool = False
    
    # CORS settings
    cors_origins: List[str] = ["http://localhost:5173", "https://hypa.app"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: List[str] = ["*"]
    
    # Rate limiting
    rate_limit_default: str = "10/minute"
    rate_limit_error_message: str = "Rate limit exceeded"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "app.log"
    
    # Cache settings
    cache_maxsize: int = 100
    cache_ttl_seconds: int = 600  # 10 minutes default
    
    # Fetching settings
    fetch_timeout: int = 10
    fetch_user_agent: str = "Mozilla/5.0 (compatible; LinkPreview/1.0)"
    fetch_follow_redirects: bool = True
    
    # Environment
    environment: str = "development"  # development, staging, production
    
    model_config = SettingsConfigDict(
        env_file=".env",  # Load from .env file if it exists
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields in env file
    )
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"


# Create a single instance of settings
settings = Settings()