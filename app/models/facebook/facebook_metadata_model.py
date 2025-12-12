from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any, List, AsyncGenerator


# =============================================
# Pydantic Models cho API
# =============================================
class ScrapeRequest(BaseModel):
    urls: List[str]
    batch_size: Optional[int] = 5
    enable_images: Optional[bool] = True
    headless: Optional[bool] = True
    max_concurrent: Optional[int] = 5
    cache_ttl: Optional[int] = 600
    mode: Optional[str] = "simple"  # simple|full|super
    
    @field_validator('urls')
    @classmethod
    def validate_urls(cls, v):
        if not v:
            raise ValueError('URLs cannot be empty')
        if len(v) > 50:  # Limit to prevent abuse
            raise ValueError('Too many URLs. Maximum 50 URLs allowed.')
        for url in v:
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f'Invalid URL format: {url}')
        return v


class ScraperConfig(BaseModel):
    headless: Optional[bool] = True
    max_concurrent: Optional[int] = 5
    cache_ttl: Optional[int] = 600
    enable_images: Optional[bool] = True
    mode: Optional[str] = "simple"  # simple|full|super