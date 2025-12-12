# -*- coding: utf-8 -*-
import time
import asyncio
import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

from .metrics import increment_rate_limits


class RateLimiter:
    """Rate limiter with per-worker capability and burst support"""

    def __init__(self, max_requests_per_minute: int = 30, max_concurrent: int = 6, burst_size: int = 5, burst_window: float = 1.0):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_concurrent = max_concurrent
        self.burst_size = burst_size  # Allow burst of N requests
        self.burst_window = burst_window  # within this time window (seconds)
        self._timestamps = deque()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()  # For thread-safe timestamp operations

    async def acquire(self):
        await self._semaphore.acquire()
        async with self._lock:
            now = time.time()
            # Remove timestamps older than 1 minute
            while self._timestamps and now - self._timestamps[0] > 60:
                self._timestamps.popleft()
            
            # Check if we've reached the rate limit
            if len(self._timestamps) >= self.max_requests_per_minute:
                oldest = self._timestamps[0]
                wait_time = 60 - (now - oldest)
                if wait_time > 0:
                    # Count this as a rate limit event
                    increment_rate_limits()
                    # Release semaphore temporarily while waiting
                    self._semaphore.release()
                    await asyncio.sleep(wait_time + 0.05)
                    # Re-acquire semaphore after waiting
                    await self._semaphore.acquire()
                    # Update time after sleep
                    now = time.time()
            
            # Add current timestamp
            self._timestamps.append(now)

    def release(self):
        try:
            self._semaphore.release()
        except Exception:
            pass  # Semaphore might already be released


class PerWorkerRateLimiter:
    """Rate limiter that can be used per worker with shared global limits"""

    def __init__(self, max_requests_per_minute: int = 30, max_concurrent: int = 6, burst_size: int = 5, burst_window: float = 1.0):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_concurrent = max_concurrent
        self.burst_size = burst_size
        self.burst_window = burst_window
        self._timestamps = deque()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()  # For thread-safe timestamp operations

    async def acquire(self):
        await self._semaphore.acquire()
        async with self._lock:
            now = time.time()
            # Remove timestamps older than 1 minute
            while self._timestamps and now - self._timestamps[0] > 60:
                self._timestamps.popleft()
            
            # Check if we've reached the rate limit
            if len(self._timestamps) >= self.max_requests_per_minute:
                oldest = self._timestamps[0]
                wait_time = 60 - (now - oldest)
                if wait_time > 0:
                    # Count this as a rate limit event
                    increment_rate_limits()
                    # Release semaphore temporarily while waiting
                    self._semaphore.release()
                    await asyncio.sleep(wait_time + 0.05)
                    # Re-acquire semaphore after waiting
                    await self._semaphore.acquire()
                    # Update time after sleep
                    now = time.time()
            
            # Add current timestamp
            self._timestamps.append(now)

    def release(self):
        try:
            self._semaphore.release()
        except Exception:
            pass  # Semaphore might already be released