# File mới: app/config/facebook_config.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import os

class FacebookScraperConfig(BaseModel):
    """Configuration model cho Facebook scraper"""

    # Browser settings
    headless: bool = Field(default=True, description="Chạy browser ở chế độ ẩn")
    browser_type: str = Field(default="chromium", description="Loại browser: chromium, firefox, webkit")

    # Performance settings
    max_concurrent: int = Field(default=5, ge=1, le=50, description="Số concurrent requests tối đa")
    timeout: int = Field(default=30000, ge=5000, description="Timeout cho mỗi request (ms)")
    navigation_timeout: int = Field(default=15000, ge=3000, description="Navigation timeout")

    # Cache settings
    cache_ttl: int = Field(default=300, ge=60, description="Cache TTL (giây)")
    max_cache_size: int = Field(default=1000, ge=100, description="Số cache entries tối đa")

    # Content settings
    enable_images: bool = Field(default=False, description="Tải images")
    enable_javascript: bool = Field(default=True, description="Kích hoạt JavaScript")
    block_trackers: bool = Field(default=True, description="Chặn tracking requests")

    # Proxy settings
    proxy_server: Optional[str] = Field(default=None, description="Proxy server URL")
    proxy_bypass: List[str] = Field(default=[], description="Domains bypass proxy")

    # Anti-detection
    rotate_user_agents: bool = Field(default=True, description="Xoay user agents")
    random_delays: bool = Field(default=True, description="Thêm delay ngẫu nhiên")
    viewport_width: int = Field(default=1280, description="Browser width")
    viewport_height: int = Field(default=720, description="Browser height")

    # Advanced settings
    retry_attempts: int = Field(default=2, ge=0, le=5, description="Số lần retry")
    wait_for_selector: Optional[str] = Field(default=None, description="Selector đợi trước khi scrape")

    @validator('proxy_server')
    def validate_proxy(cls, v):
        if v and not v.startswith(('http://', 'https://', 'socks5://')):
            raise ValueError('Proxy phải bắt đầu với http://, https:// hoặc socks5://')
        return v

    @classmethod
    def from_env(cls):
        """Load config từ environment variables"""
        return cls(
            headless=os.getenv('FB_HEADLESS', 'true').lower() == 'true',
            max_concurrent=int(os.getenv('FB_MAX_CONCURRENT', '5')),
            timeout=int(os.getenv('FB_TIMEOUT', '30000')),
            cache_ttl=int(os.getenv('FB_CACHE_TTL', '300')),
            enable_images=os.getenv('FB_ENABLE_IMAGES', 'false').lower() == 'true',
            proxy_server=os.getenv('FB_PROXY_SERVER'),
        )