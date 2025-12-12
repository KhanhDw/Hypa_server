import time
import math
import asyncio
from typing import Dict, Optional
from enum import Enum

from .metrics import (
    FACEBOOK_NAVIGATION_DURATION,
    FACEBOOK_CACHE_MISSES,
    FACEBOOK_RATE_LIMITS
)
from .anomaly_detector import anomaly_detector


class ThrottleReason(Enum):
    NAVIGATION_LATENCY = "navigation_latency"
    CACHE_MISS_RATE = "cache_miss_rate"
    RATE_LIMIT = "rate_limit"
    MEMORY_HIGH = "memory_high"
    NONE = "none"


class AdaptiveThrottler:
    """
    Adaptive throttling system that adjusts scraping speed based on:
    - Navigation duration increases
    - Cache miss rate
    - Rate limit events
    Uses logarithmic/exponential backoff to avoid queue swelling
    """
    
    def __init__(self, 
                 base_delay: float = 0.05,  # Reduced base delay for better throughput
                 max_delay: float = 3.0,    # Reduced max delay for better responsiveness
                 latency_threshold: float = 2.0,  # Lower threshold for faster response
                 cache_miss_threshold: float = 0.6,  # Lower threshold for cache misses
                 memory_threshold: float = 800.0):  # Memory threshold in MB
    
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.latency_threshold = latency_threshold
        self.cache_miss_threshold = cache_miss_threshold
        self.memory_threshold = memory_threshold
        
        # Track historical metrics
        self.navigation_durations = []
        self.cache_miss_events = []
        self.rate_limit_events = []
        self.memory_usage = []
        
        # Window sizes for calculation - adjusted for large batch processing
        self.duration_window_size = 15  # Smaller window for faster adaptation
        self.event_window_size = 20    # Smaller window for faster adaptation
        self.memory_window_size = 8    # Smaller window for faster adaptation
        
        # Current throttle state
        self.current_delay = base_delay
        self.last_throttle_time = time.time()
        self.throttle_reason = ThrottleReason.NONE
        self.throttle_multiplier = 1.0  # Multiplier for exponential backoff
        self.active_throttle_until = 0  # Unix timestamp when throttle ends
        
        # Track recent anomalies
        self.recent_anomalies = []
        
    def update_navigation_time(self, duration: float, mode: str = "simple") -> float:
        """
        Update with new navigation duration and return suggested delay
        """
        # Add to duration history
        self.navigation_durations.append((time.time(), duration))
        
        # Keep only recent values
        self._trim_window(self.navigation_durations, self.duration_window_size)
        
        # Check for anomalies using the detector
        anomaly_result = anomaly_detector.add_navigation_time(duration, mode)
        
        # Calculate suggested delay based on navigation time
        avg_duration = self._get_recent_avg_duration()
        if avg_duration > self.latency_threshold:
            # Use logarithmic backoff for high navigation times
            multiplier = 1 + math.log(max(1, avg_duration / self.latency_threshold))
            suggested_delay = min(self.base_delay * multiplier, self.max_delay)
            self._apply_throttle(suggested_delay, ThrottleReason.NAVIGATION_LATENCY)
        
        return self.current_delay
    
    def update_cache_stats(self, cache_hit: bool) -> float:
        """
        Update with cache hit/miss and return suggested delay
        """
        current_time = time.time()
        is_miss = not cache_hit
        self.cache_miss_events.append((current_time, is_miss))
        
        # Keep only recent values
        self._trim_window(self.cache_miss_events, self.event_window_size)
        
        # Calculate cache miss rate
        miss_rate = self._get_cache_miss_rate()
        
        if miss_rate > self.cache_miss_threshold:
            # Use logarithmic backoff for high cache miss rates
            multiplier = 1 + math.log(max(1, miss_rate / self.cache_miss_threshold))
            suggested_delay = min(self.base_delay * multiplier, self.max_delay)
            self._apply_throttle(suggested_delay, ThrottleReason.CACHE_MISS_RATE)
        
        return self.current_delay
    
    def record_rate_limit_event(self) -> float:
        """
        Record a rate limit event and return suggested delay
        """
        current_time = time.time()
        self.rate_limit_events.append(current_time)
        
        # Keep only recent values
        self._trim_window(self.rate_limit_events, self.event_window_size)
        
        # Use the anomaly detector to track rate limits
        anomaly_result = anomaly_detector.add_rate_limit_event()
        
        # Apply more aggressive throttling for rate limit events
        if anomaly_result['rate_limit_spike'] or anomaly_result['high_rate_limit_frequency']:
            # Exponential backoff for rate limit events
            self.throttle_multiplier = min(self.throttle_multiplier * 1.5, 10.0)
            suggested_delay = min(self.base_delay * self.throttle_multiplier, self.max_delay)
            self._apply_throttle(suggested_delay, ThrottleReason.RATE_LIMIT)
        
        return self.current_delay
    
    def update_memory_usage(self, memory_mb: float, browser_id: str = "default") -> float:
        """
        Update with memory usage and return suggested delay
        """
        current_time = time.time()
        self.memory_usage.append((current_time, memory_mb))
        
        # Keep only recent values
        self._trim_window(self.memory_usage, self.memory_window_size)
        
        # Check if memory usage is high
        if memory_mb > self.memory_threshold:
            # Add to anomaly detector
            anomaly_result = anomaly_detector.add_memory_usage(memory_mb, browser_id)
            
            if anomaly_result['memory_high'] or anomaly_result['memory_anomaly']:
                # Moderate throttling for high memory usage
                suggested_delay = min(self.base_delay * 2.0, self.max_delay)
                self._apply_throttle(suggested_delay, ThrottleReason.MEMORY_HIGH)
        
        return self.current_delay
    
    def get_current_delay(self) -> float:
        """
        Get the current delay, applying decay if no throttle is active
        """
        current_time = time.time()
        
        # If throttle period has ended, gradually reduce delay
        if current_time > self.active_throttle_until:
            if self.current_delay > self.base_delay:
                # Apply gradual decay
                decay_factor = 0.95  # Slow decay
                self.current_delay = max(self.base_delay, self.current_delay * decay_factor)
        
        return self.current_delay
    
    def apply_throttle(self) -> None:
        """
        Apply throttle delay asynchronously
        """
        delay = self.get_current_delay()
        if delay > 0:
            # This would be called from an async context, so we return the delay
            # The actual sleep would happen in the calling function
            pass
    
    def _apply_throttle(self, suggested_delay: float, reason: ThrottleReason) -> None:
        """
        Internal method to apply throttling with exponential backoff
        """
        self.current_delay = suggested_delay
        self.throttle_reason = reason
        self.active_throttle_until = time.time() + (suggested_delay * 3)  # Throttle for 3x the delay period
        
    def _trim_window(self, data_list: list, window_size: int) -> None:
        """
        Trim the list to keep only the most recent values
        """
        if len(data_list) > window_size:
            data_list[:] = data_list[-window_size:]
    
    def _get_recent_avg_duration(self) -> float:
        """
        Calculate average of recent navigation durations
        """
        if not self.navigation_durations:
            return 0.0
        
        recent_durations = [duration for _, duration in self.navigation_durations]
        return sum(recent_durations) / len(recent_durations)
    
    def _get_cache_miss_rate(self) -> float:
        """
        Calculate cache miss rate from recent events
        """
        if not self.cache_miss_events:
            return 0.0
        
        miss_count = sum(1 for _, is_miss in self.cache_miss_events if is_miss)
        return miss_count / len(self.cache_miss_events)


# Global instance for use in other modules
throttler = AdaptiveThrottler()