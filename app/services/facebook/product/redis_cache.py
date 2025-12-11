# -*- coding: utf-8 -*-
import logging
import asyncio
import json
import hashlib
import redis.asyncio as redis
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, redis_url="redis://localhost:6379", ttl=300):
        self.redis_url = redis_url
        self.ttl = ttl
        self._redis = None

    async def connect(self):
        self._redis = redis.from_url(
            self.redis_url,
            decode_responses=True,
            max_connections=20
        )

    def _get_cache_key(self, url: str) -> str:
        return f"fb_scrape:{hashlib.md5(url.encode()).hexdigest()}"

    async def get(self, url: str):
        if not self._redis:
            return None
        key = self._get_cache_key(url)
        data = await self._redis.get(key)
        return json.loads(data) if data else None

    async def set(self, url: str, data: dict, ttl=None):
        if not self._redis:
            return
        key = self._get_cache_key(url)
        ttl = ttl or self.ttl
        await self._redis.set(key, json.dumps(data, ensure_ascii=False), ex=ttl)

    async def close(self):
        if self._redis:
            await self._redis.close()