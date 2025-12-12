import time
import math
from typing import Dict, List, Optional, Tuple
from collections import deque
import statistics

from .metrics import (
    FACEBOOK_NAVIGATION_DURATION,
    FACEBOOK_RATE_LIMITS,
    FACEBOOK_BROWSER_MEMORY,
    increment_rate_limits,
    increment_checkpoints
)


class EWMA:
    """Exponentially Weighted Moving Average for anomaly detection"""
    
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.value = None
        self.initialized = False
    
    def update(self, new_value: float) -> float:
        if not self.initialized:
            self.value = new_value
            self.initialized = True
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value
        return self.value
    
    def get_value(self) -> Optional[float]:
        return self.value


class ZScoreDetector:
    """Z-score based anomaly detector with rolling window"""
    
    def __init__(self, window_size: int = 50, threshold: float = 2.0):
        self.window_size = window_size
        self.threshold = threshold
        self.values = deque(maxlen=window_size)
    
    def update(self, new_value: float) -> Tuple[float, bool]:  # (z_score, is_anomaly)
        self.values.append(new_value)
        
        if len(self.values) < 10:  # Need minimum values for statistics
            return 0.0, False
        
        mean = statistics.mean(self.values)
        stdev = statistics.stdev(self.values) if len(self.values) > 1 else 0.0
        
        if stdev == 0:
            return 0.0, False
        
        z_score = abs(new_value - mean) / stdev
        is_anomaly = z_score > self.threshold
        
        return z_score, is_anomaly


class AnomalyDetector:
    """
    Anomaly detection for Facebook scraper metrics
    Detects: latency spikes, rate-limit spikes, memory abnormalities
    """
    
    def __init__(self, 
                 latency_threshold: float = 2.0,  # Z-score threshold
                 rate_limit_window: int = 60,      # Time window in seconds
                 memory_threshold: float = 1024): # Memory threshold in MB
    
        # Z-score detectors for different metrics
        self.latency_detector = ZScoreDetector(threshold=latency_threshold)
        self.rate_limit_detector = ZScoreDetector(threshold=latency_threshold)
        self.memory_detector = ZScoreDetector(threshold=latency_threshold)
        
        # Rate limit tracking (per minute)
        self.rate_limit_counts = deque()
        self.rate_limit_window = rate_limit_window
        
        # Memory tracking
        self.memory_threshold = memory_threshold
        
        # Event tracking
        self.last_navigation_time = time.time()
        self.last_rate_limit_time = time.time()
        self.anomaly_events = deque(maxlen=100)  # Keep last 100 events
        
        # EWMA for smoother anomaly detection
        self.latency_ewma = EWMA(alpha=0.3)
        self.rate_limit_ewma = EWMA(alpha=0.3)
        self.memory_ewma = EWMA(alpha=0.3)
    
    def add_navigation_time(self, duration: float, mode: str = "simple") -> Dict[str, bool]:
        """
        Add navigation time for anomaly detection
        Returns dict with anomaly status for different checks
        """
        current_time = time.time()
        
        # Update EWMA
        ewma_value = self.latency_ewma.update(duration)
        
        # Check for anomalies
        z_score, is_latency_anomaly = self.latency_detector.update(duration)
        
        # Store event
        event = {
            'type': 'navigation_latency',
            'timestamp': current_time,
            'value': duration,
            'ewma_value': ewma_value,
            'z_score': z_score,
            'is_anomaly': is_latency_anomaly,
            'mode': mode
        }
        
        self.anomaly_events.append(event)
        
        return {
            'latency_spike': is_latency_anomaly,
            'ewma_high': ewma_value > 5.0 if ewma_value else False  # If EWMA shows high values
        }
    
    def add_rate_limit_event(self) -> Dict[str, bool]:
        """
        Record a rate limit event and check for anomalies
        """
        current_time = time.time()
        self.rate_limit_counts.append(current_time)
        
        # Remove events older than the window
        cutoff_time = current_time - self.rate_limit_window
        while self.rate_limit_counts and self.rate_limit_counts[0] < cutoff_time:
            self.rate_limit_counts.popleft()
        
        # Count rate limits in the current window
        rate_limits_in_window = len(self.rate_limit_counts)
        
        # Update EWMA
        ewma_value = self.rate_limit_ewma.update(rate_limits_in_window)
        
        # Check for anomalies
        z_score, is_rate_limit_anomaly = self.rate_limit_detector.update(rate_limits_in_window)
        
        # Store event
        event = {
            'type': 'rate_limit',
            'timestamp': current_time,
            'value': rate_limits_in_window,
            'ewma_value': ewma_value,
            'z_score': z_score,
            'is_anomaly': is_rate_limit_anomaly
        }
        
        self.anomaly_events.append(event)
        
        return {
            'rate_limit_spike': is_rate_limit_anomaly,
            'high_rate_limit_frequency': rate_limits_in_window > 10,  # More than 10 per minute
            'ewma_high': ewma_value > 5.0 if ewma_value else False
        }
    
    def add_memory_usage(self, memory_mb: float, browser_id: str = "default") -> Dict[str, bool]:
        """
        Record memory usage and check for anomalies
        """
        current_time = time.time()
        
        # Update EWMA
        ewma_value = self.memory_ewma.update(memory_mb)
        
        # Check for anomalies
        z_score, is_memory_anomaly = self.memory_detector.update(memory_mb)
        
        # Check absolute threshold
        is_memory_high = memory_mb > self.memory_threshold
        
        # Store event
        event = {
            'type': 'memory_usage',
            'timestamp': current_time,
            'value': memory_mb,
            'ewma_value': ewma_value,
            'z_score': z_score,
            'is_anomaly': is_memory_anomaly,
            'is_high': is_memory_high,
            'browser_id': browser_id
        }
        
        self.anomaly_events.append(event)
        
        return {
            'memory_anomaly': is_memory_anomaly,
            'memory_high': is_memory_high,
            'ewma_high': ewma_value > self.memory_threshold * 0.8 if ewma_value else False
        }
    
    def get_recent_anomalies(self, minutes: int = 5) -> List[Dict]:
        """
        Get anomalies from the last N minutes
        """
        current_time = time.time()
        cutoff_time = current_time - (minutes * 60)
        
        recent = [event for event in self.anomaly_events if event['timestamp'] > cutoff_time]
        return recent
    
    def get_anomaly_summary(self) -> Dict:
        """
        Get a summary of current anomaly status
        """
        recent_events = self.get_recent_anomalies(5)  # Last 5 minutes
        
        summary = {
            'total_anomalies': len([e for e in recent_events if e['is_anomaly']]),
            'navigation_anomalies': len([e for e in recent_events if e['type'] == 'navigation_latency' and e['is_anomaly']]),
            'rate_limit_anomalies': len([e for e in recent_events if e['type'] == 'rate_limit' and e['is_anomaly']]),
            'memory_anomalies': len([e for e in recent_events if e['type'] == 'memory_usage' and e['is_anomaly']]),
            'high_memory_events': len([e for e in recent_events if e['type'] == 'memory_usage' and e['is_high']]),
            'total_events': len(recent_events)
        }
        
        return summary


# Global instance for use in other modules
anomaly_detector = AnomalyDetector()