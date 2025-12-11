# -*- coding: utf-8 -*-
import time
import asyncio
import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter using deque for O(1) pops/pushes"""

    def __init__(self, max_requests_per_minute: int = 60, max_concurrent: int = 10):
        self.max_requests_per_minute = max_requests_per_minute
        self._timestamps = deque()
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def acquire(self):
        await self._semaphore.acquire()
        now = time.time()
        # pop old
        while self._timestamps and now - self._timestamps[0] > 60:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.max_requests_per_minute:
            oldest = self._timestamps[0]
            wait_time = 60 - (now - oldest)
            if wait_time > 0:
                await asyncio.sleep(wait_time + 0.05)
        self._timestamps.append(time.time())

    def release(self):
        try:
            self._semaphore.release()
        except Exception:
            pass