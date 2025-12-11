# File mới: app/middleware/rate_limiter.py
import asyncio
from typing import Dict, Optional
import time
from dataclasses import dataclass

@dataclass
class RateLimiter:
    """Rate limiter với token bucket algorithm"""

    max_tokens: int = 100
    refill_rate: float = 10.0  # tokens per second
    bucket: Dict[str, float] = None  # client_id -> tokens
    last_refill: Dict[str, float] = None  # client_id -> timestamp

    def __post_init__(self):
        self.bucket = {}
        self.last_refill = {}

    def _refill_bucket(self, client_id: str):
        """Refill tokens cho client"""
        now = time.time()

        if client_id not in self.bucket:
            self.bucket[client_id] = self.max_tokens
            self.last_refill[client_id] = now
            return

        last_refill = self.last_refill[client_id]
        time_passed = now - last_refill
        tokens_to_add = time_passed * self.refill_rate

        if tokens_to_add > 0:
            self.bucket[client_id] = min(
                self.max_tokens,
                self.bucket[client_id] + tokens_to_add
            )
            self.last_refill[client_id] = now

    async def acquire(self, client_id: str, tokens: int = 1) -> bool:
        """Lấy tokens từ bucket"""
        self._refill_bucket(client_id)

        if self.bucket[client_id] >= tokens:
            self.bucket[client_id] -= tokens
            return True
        return False

class CircuitBreaker:
    """Circuit breaker pattern cho scraper"""

    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def execute(self, func, *args, **kwargs):
        """Execute function với circuit breaker"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()

            if self.failures >= self.failure_threshold:
                self.state = "OPEN"

            raise e