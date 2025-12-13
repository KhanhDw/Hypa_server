from prometheus_client import Counter, Gauge, Histogram
from typing import Optional
import time


# Counter metrics
FACEBOOK_SCRAPES_TOTAL = Counter(
    'facebook_scrapes_total', 
    'Total number of Facebook scrape attempts',
    ['mode']
)

FACEBOOK_SCRAPES_SUCCESS = Counter(
    'facebook_scrapes_success_total', 
    'Total number of successful Facebook scrapes',
    ['mode']
)

FACEBOOK_SCRAPES_FAILED = Counter(
    'facebook_scrapes_failed_total', 
    'Total number of failed Facebook scrapes',
    ['error_type', 'mode']
)

FACEBOOK_RATE_LIMITS = Counter(
    'facebook_rate_limits_total', 
    'Total number of Facebook rate limit events'
)

FACEBOOK_CHECKPOINTS = Counter(
    'facebook_checkpoints_total', 
    'Total number of Facebook checkpoint/restriction events'
)

FACEBOOK_CACHE_HITS = Counter(
    'facebook_cache_hits_total', 
    'Total number of cache hits',
    ['cache_type']  # 'memory' or 'redis'
)

FACEBOOK_CACHE_MISSES = Counter(
    'facebook_cache_misses_total',
    'Total number of cache misses',
    ['cache_type', 'reason']  # reason: 'not_found', 'ttl_expired', 'evicted'
)

FACEBOOK_CACHE_TTL_EXPIRY = Counter(
    'facebook_cache_ttl_expiry_total',
    'Total number of cache entries expired by TTL',
    ['cache_type']
)

FACEBOOK_CACHE_EVICTION = Counter(
    'facebook_cache_eviction_total',
    'Total number of cache entries evicted (LRU)',
    ['cache_type']
)

FACEBOOK_RESPONSE_STATUS = Counter(
    'facebook_response_status_total',
    'Facebook response status codes and types',
    ['status_type', 'mode']  # e.g., 'success', 'not_accessible', 'deleted', 'private', 'rate_limited', 'blocked', 'redirect_loop'
)

# Single-flight metrics
SINGLE_FLIGHT_REQUESTS_TOTAL = Counter(
    'single_flight_requests_total',
    'Total number of single-flight requests',
    ['type']  # 'direct', 'coalesced'
)

SINGLE_FLIGHT_TIMEOUTS_TOTAL = Counter(
    'single_flight_timeouts_total',
    'Total number of single-flight timeouts',
    ['scope']  # 'in_process', 'cross_process'
)

SINGLE_FLIGHT_COORDINATION_FAILURES = Counter(
    'single_flight_coordination_failures_total',
    'Total number of single-flight coordination failures',
    ['error_type']
)

# Gauge metrics
FACEBOOK_QUEUE_SIZE = Gauge(
    'facebook_queue_size', 
    'Current number of jobs in scraping queue'
)

FACEBOOK_ACTIVE_CONTEXTS = Gauge(
    'facebook_active_contexts', 
    'Current number of active browser contexts'
)

FACEBOOK_ACTIVE_PAGES = Gauge(
    'facebook_active_pages', 
    'Current number of active browser pages'
)

FACEBOOK_BROWSER_MEMORY = Gauge(
    'facebook_browser_memory_mb', 
    'Browser memory usage in MB',
    ['browser_id']
)

FACEBOOK_CACHE_SIZE = Gauge(
    'facebook_cache_size_current',
    'Current cache size',
    ['cache_type']
)

# Histogram metrics
FACEBOOK_SCRAPE_DURATION = Histogram(
    'facebook_scrape_duration_seconds',
    'Duration of Facebook scraping operations',
    ['mode'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, float('inf')]
)

FACEBOOK_NAVIGATION_DURATION = Histogram(
    'facebook_navigation_duration_seconds',
    'Duration of page navigation operations',
    ['mode'],  # Added mode label as suggested
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float('inf')]
)

FACEBOOK_EXTRACTION_DURATION = Histogram(
    'facebook_extraction_duration_seconds',
    'Duration of data extraction operations',
    ['mode'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float('inf')]
)

FACEBOOK_QUEUE_WAITING_DURATION = Histogram(
    'facebook_queue_waiting_duration_seconds',
    'Time jobs spend waiting in queue before processing',
    ['mode'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float('inf')]
)

FACEBOOK_WORKER_IDLE_DURATION = Histogram(
    'facebook_worker_idle_duration_seconds',
    'Time workers spend idle between tasks',
    buckets=[0.01, 0.1, 0.5, 1.0, 2.0, 5.0, float('inf')]
)

# Single-flight histogram metrics
SINGLE_FLIGHT_COORDINATION_DURATION = Histogram(
    'single_flight_coordination_duration_seconds',
    'Duration of single-flight coordination operations',
    ['scope'],  # 'in_process', 'cross_process'
    buckets=[0.001, 0.01, 0.1, 0.5, 1.0, 5.0, float('inf')]
)

SINGLE_FLIGHT_LATENCY_SAVINGS = Histogram(
    'single_flight_latency_savings_seconds',
    'Time saved by single-flight coalescing',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, float('inf')]
)


# Helper functions for metric collection
def increment_scrape_attempts(mode: str):
    FACEBOOK_SCRAPES_TOTAL.labels(mode=mode).inc()

def increment_scrape_success(mode: str):
    FACEBOOK_SCRAPES_SUCCESS.labels(mode=mode).inc()

def increment_scrape_failure(error_type: str, mode: str):
    FACEBOOK_SCRAPES_FAILED.labels(error_type=error_type, mode=mode).inc()

def increment_rate_limits():
    FACEBOOK_RATE_LIMITS.inc()

def increment_checkpoints():
    FACEBOOK_CHECKPOINTS.inc()

def increment_cache_hit(cache_type: str):
    FACEBOOK_CACHE_HITS.labels(cache_type=cache_type).inc()

def increment_cache_miss(cache_type: str, reason: str):
    FACEBOOK_CACHE_MISSES.labels(cache_type=cache_type, reason=reason).inc()

def increment_cache_ttl_expiry(cache_type: str):
    FACEBOOK_CACHE_TTL_EXPIRY.labels(cache_type=cache_type).inc()

def increment_cache_eviction(cache_type: str):
    FACEBOOK_CACHE_EVICTION.labels(cache_type=cache_type).inc()

def increment_response_status(status_type: str, mode: str):
    FACEBOOK_RESPONSE_STATUS.labels(status_type=status_type, mode=mode).inc()

def update_queue_size(size: int):
    FACEBOOK_QUEUE_SIZE.set(size)

def update_active_contexts(count: int):
    FACEBOOK_ACTIVE_CONTEXTS.set(count)

def update_active_pages(count: int):
    FACEBOOK_ACTIVE_PAGES.set(count)

def update_browser_memory(memory_mb: float, browser_id: str = "default"):
    FACEBOOK_BROWSER_MEMORY.labels(browser_id=browser_id).set(memory_mb)

def update_cache_size(size: int, cache_type: str):
    FACEBOOK_CACHE_SIZE.labels(cache_type=cache_type).set(size)

def observe_scrape_duration(duration: float, mode: str):
    FACEBOOK_SCRAPE_DURATION.labels(mode=mode).observe(duration)

def observe_navigation_duration(duration: float, mode: str):
    FACEBOOK_NAVIGATION_DURATION.labels(mode=mode).observe(duration)

def observe_extraction_duration(duration: float, mode: str):
    FACEBOOK_EXTRACTION_DURATION.labels(mode=mode).observe(duration)

def observe_queue_waiting_duration(duration: float, mode: str):
    FACEBOOK_QUEUE_WAITING_DURATION.labels(mode=mode).observe(duration)

def observe_worker_idle_duration(duration: float):
    FACEBOOK_WORKER_IDLE_DURATION.observe(duration)

# Single-flight helper functions
def increment_single_flight_requests(request_type: str):
    SINGLE_FLIGHT_REQUESTS_TOTAL.labels(type=request_type).inc()

def increment_single_flight_timeouts(scope: str):
    SINGLE_FLIGHT_TIMEOUTS_TOTAL.labels(scope=scope).inc()

def increment_single_flight_coordination_failures(error_type: str):
    SINGLE_FLIGHT_COORDINATION_FAILURES.labels(error_type=error_type).inc()

def observe_single_flight_coordination_duration(duration: float, scope: str):
    SINGLE_FLIGHT_COORDINATION_DURATION.labels(scope=scope).observe(duration)

def observe_single_flight_latency_savings(duration: float):
    SINGLE_FLIGHT_LATENCY_SAVINGS.observe(duration)