# -*- coding: utf-8 -*-
import time
import logging
import asyncio
import json
import hashlib
import os
from typing import Optional, Dict, Any, List, AsyncGenerator, Callable
from collections import OrderedDict, defaultdict
import redis.asyncio as redis

logger = logging.getLogger(__name__)

from .redis_cache import RedisCache
from .rate_limiter import RateLimiter
from .fetcher import PageFetcher
from .extractor import DataExtractor
from .metrics import (
    increment_scrape_attempts, increment_scrape_success, increment_scrape_failure,
    increment_cache_hit, increment_cache_miss, update_queue_size,
    observe_scrape_duration, observe_queue_waiting_duration
)
from .anomaly_detector import anomaly_detector
from .throttler import throttler
from .scaler import scaler


class PureSingleFlight:
    """
    Pure single-flight implementation: for a key, guarantee only one fn runs at a time
    Does NOT handle:
    - Caching
    - Redis coordination
    - Result handling
    Only does: coordination and execution
    """
    
    def __init__(self, timeout: float = 45.0):
        self.timeout = timeout
        self._futures: Dict[str, asyncio.Future] = {}
        self._locks = defaultdict(asyncio.Lock)
    
    async def do(self, key: str, fn: Callable, *args, **kwargs):
        """
        Execute fn with single-flight semantics
        All other concerns (cache, Redis, etc.) handled outside
        """
        async with self._locks[key]:
            if key in self._futures:
                # Another request is in flight
                future = self._futures[key]
            else:
                # We're the leader
                future = asyncio.Future()
                self._futures[key] = future
                
                # Execute OUTSIDE lock
                asyncio.create_task(self._execute_and_cleanup(key, future, fn, *args, **kwargs))
        
        try:
            return await asyncio.wait_for(future, timeout=self.timeout)
        except asyncio.TimeoutError:
            # Cleanup timeout
            async with self._locks[key]:
                self._futures.pop(key, None)
            raise
    
    async def _execute_and_cleanup(self, key: str, future: asyncio.Future,
                                  fn: Callable, *args, **kwargs):
        """Execute fn and ensure cleanup"""
        try:
            result = await fn(*args, **kwargs)
            if not future.done():
                future.set_result(result)
        except Exception as e:
            if not future.done():
                future.set_exception(e)
        finally:
            # Always cleanup
            if future.done():
                self._futures.pop(key, None)


class RedisCoordination:
    """
    Redis coordination using Pub/Sub + lock renewal
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379", lock_timeout: int = 30):
        self.redis_url = redis_url
        self.lock_timeout = lock_timeout
        self._redis = None
        self._pubsub = None
        self._lock_renewal_tasks = {}
        self._process_id = f"proc_{os.getpid()}_{int(time.time())}"
    
    async def connect(self):
        try:
            if self._redis is None:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
            if self._pubsub is None:
                self._pubsub = self._redis.pubsub()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis at {self.redis_url}: {e}")
            return False
    
    async def execute_with_coordination(self, url: str, fn: Callable, *args, **kwargs):
        """
        Execute with cross-process coordination using Pub/Sub
        """
        # Make sure Redis is available
        if not self._redis:
            logger.info("Redis connection not available, falling back to in-process only")
            # Execute function directly if Redis is not available
            return await fn(*args, **kwargs)
            
        cache_key = f"single_flight:{hashlib.md5(url.encode()).hexdigest()}"
        lock_key = f"{cache_key}:lock"
        channel_key = f"{cache_key}:channel"
        
        # Try to acquire leader lock
        try:
            is_leader = await self._redis.set(lock_key, self._process_id, nx=True, ex=self.lock_timeout)
        except Exception as e:
            logger.error(f"Failed to acquire Redis lock: {e}")
            # If Redis lock fails, execute function directly
            return await fn(*args, **kwargs)
        
        if is_leader:
            return await self._execute_as_leader(lock_key, channel_key, fn, *args, **kwargs)
        else:
            return await self._wait_as_follower(channel_key)
    
    async def _execute_as_leader(self, lock_key: str, channel_key: str,
                                fn: Callable, *args, **kwargs):
        """
        Execute as leader with lock renewal and result broadcasting
        """
        # Start lock renewal task
        renewal_task = asyncio.create_task(self._renew_lock(lock_key))
        self._lock_renewal_tasks[lock_key] = renewal_task
        
        try:
            # Execute the actual work
            result = await fn(*args, **kwargs)
            
            # Publish result to channel for followers if Redis is available
            if self._redis:
                try:
                    await self._redis.publish(channel_key, json.dumps(result, ensure_ascii=False))
                except Exception as e:
                    logger.error(f"Failed to publish result to Redis: {e}")
            
            return result
        except Exception as e:
            # If there's an error, publish error result so followers know if Redis is available
            error_result = {
                "url": args[0] if args else "unknown",
                "error": str(e),
                "success": False,
                "error_type": "coordination_error"
            }
            if self._redis:
                try:
                    await self._redis.publish(channel_key, json.dumps(error_result, ensure_ascii=False))
                except Exception as publish_error:
                    logger.error(f"Failed to publish error result to Redis: {publish_error}")
            raise
        finally:
            # Stop renewal and clean up
            renewal_task.cancel()
            try:
                await renewal_task
            except asyncio.CancelledError:
                pass
            
            # Clean up lock (not result - let it persist briefly for late followers) if Redis is available
            if self._redis:
                try:
                    await self._redis.delete(lock_key)
                except Exception as e:
                    logger.error(f"Failed to delete lock: {e}")
            self._lock_renewal_tasks.pop(lock_key, None)
    
    async def _renew_lock(self, lock_key: str):
        """
        Renew lock periodically to prevent split-brain
        """
        while True:
            try:
                # Wait for a bit before renewal
                await asyncio.sleep(self.lock_timeout // 3)  # Renew every 1/3 TTL
                # Only renew if Redis is still available
                if not self._redis:
                    break
                renewed = await self._redis.expire(lock_key, self.lock_timeout)
                if not renewed:
                    # Lock was lost, something's wrong
                    logger.warning(f"Lost lock {lock_key}, stopping renewal")
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error renewing lock {lock_key}: {e}")
                # If Redis error occurred, break the loop
                break
    
    async def _wait_as_follower(self, channel_key: str):
        """
        Wait as follower using Pub/Sub (no polling)
        """
        # Make sure Pub/Sub is available
        if not self._pubsub:
            logger.error("Redis Pub/Sub not available, coordination failed")
            raise Exception("Redis Pub/Sub not available")
            
        # Subscribe to channel
        try:
            await self._pubsub.subscribe(channel_key)
        except Exception as e:
            logger.error(f"Failed to subscribe to Redis channel: {e}")
            raise
        
        try:
            # Wait for message or timeout
            start_time = time.time()
            while time.time() - start_time < 45.0:
                try:
                    message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message['data']:
                        return json.loads(message['data'])
                except Exception as e:
                    logger.error(f"Error receiving message from Redis: {e}")
                    raise
            raise TimeoutError(f"Timeout waiting for result on {channel_key}")
        except asyncio.TimeoutError:
            try:
                await self._pubsub.unsubscribe(channel_key)
            except:
                pass  # Ignore unsubscribe errors
            raise
        finally:
            try:
                await self._pubsub.unsubscribe(channel_key)
            except:
                pass  # Ignore unsubscribe errors


class FacebookCacheManager:
    """
    Structured cache management with clear responsibility
    """
    
    def __init__(self, redis_cache_instance, local_cache, cache_ttl: int = 300):
        self.redis_cache = redis_cache_instance  # RedisCache instance
        self.local_cache = local_cache
        self.cache_ttl = cache_ttl
        self.negative_cache_ttl = 30  # Short TTL for negative results
    
    async def get_with_negative_cache(self, url: str) -> Optional[Dict]:
        """Get result, including negative results"""
        # Check local cache first
        if self.local_cache:
            local_result = self.local_cache.get(url)
            if local_result:
                return local_result
        
        # Check Redis cache
        if self.redis_cache and hasattr(self.redis_cache, '_redis') and self.redis_cache._redis:
            try:
                redis_result = await self.redis_cache.get(url)
                if redis_result:
                    # Cache in local for fast access
                    if self.local_cache:
                        self.local_cache.set(url, redis_result, self.cache_ttl)
                    return redis_result
            except Exception:
                logger.debug("Redis cache get failed", exc_info=True)
        
        return None
    
    async def store_result(self, url: str, result: Dict):
        """Store positive result"""
        # Store in local cache
        if self.local_cache and url and result:
            self.local_cache.set(url, result, self.cache_ttl)
        
        # Store in Redis if available
        if self.redis_cache and url and result:
            try:
                await self.redis_cache.set(url, result, self.cache_ttl)
            except Exception:
                logger.debug("Redis set failed", exc_info=True)
    
    async def store_negative_result(self, url: str, error_info: Dict):
        """Store negative result (error) to prevent repeated attempts"""
        negative_result = {
            "success": False,
            "error_type": error_info.get("type", "unknown") if error_info else "unknown",
            "error_message": error_info.get("message", "Unknown error") if error_info else "Unknown error",
            "timestamp": time.time(),
            "from_cache": True,
            "scrape_time": 0
        }
        
        # Store in local cache (short TTL)
        if self.local_cache and url:
            self.local_cache.set(url, negative_result, self.negative_cache_ttl)
        
        # Store in Redis cache if available (short TTL)
        if self.redis_cache and url:
            try:
                await self.redis_cache.set(url, negative_result, self.negative_cache_ttl)
            except Exception:
                logger.debug("Redis negative result set failed", exc_info=True)
    
    async def _get_redis_result(self, url: str) -> Optional[Dict]:
        """Get result from Redis"""
        if not self.redis_cache or not hasattr(self.redis_cache, '_redis') or not self.redis_cache._redis:
            return None
            
        try:
            result = await self.redis_cache.get(url)
            if result:
                # Check if this is a negative result that hasn't expired
                if not result.get("success") and "timestamp" in result:
                    ttl = result.get("ttl", self.negative_cache_ttl)
                    timestamp = result.get("timestamp", 0)
                    if time.time() - timestamp < ttl:
                        return result
                elif result.get("success"):
                    return result
        except Exception:
            logger.debug("Redis get failed in _get_redis_result", exc_info=True)
        
        return None


class SharedInMemoryCache:
    """
    Shared in-memory cache to reduce Redis calls
    """
    def __init__(self, max_size: int = 1000):  # Increase cache size
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        # Track TTL expiry and eviction
        self.expiry_count = 0
        self.eviction_count = 0

    def get(self, url: str) -> Optional[Dict]:
        if not url:
            return None
            
        cache_key = f"fb_scrape:{hashlib.md5(url.encode()).hexdigest()}"
        if cache_key in self.cache:
            # Check TTL expiry
            entry = self.cache[cache_key]
            if time.time() - entry.get('timestamp', 0) > entry.get('ttl', 600):  # Increase TTL to 10 minutes
                # Entry expired, remove it
                self.cache.pop(cache_key)
                self.expiry_count += 1
                try:
                    from .metrics import increment_cache_ttl_expiry
                    increment_cache_ttl_expiry('memory')
                except:
                    pass  # Ignore metrics errors
                return None
                
            self.hits += 1
            # Move to end (most recently used)
            value = self.cache.pop(cache_key)
            self.cache[cache_key] = value
            try:
                from .metrics import increment_cache_hit
                increment_cache_hit('memory')
            except:
                pass  # Ignore metrics errors
            return value
        self.misses += 1
        try:
            from .metrics import increment_cache_miss
            increment_cache_miss('memory', 'not_found')
        except:
            pass  # Ignore metrics errors
        return None

    def set(self, url: str, data: Dict, ttl: int = 600):  # Increase TTL to 10 minutes
        if not url or not data:
            return
            
        cache_key = f"fb_scrape:{hashlib.md5(url.encode()).hexdigest()}"
        entry = {
            'data': data,
            'timestamp': time.time(),
            'ttl': ttl
        }
        if len(self.cache) >= self.max_size:
            # Remove oldest item
            oldest_key = next(iter(self.cache))
            self.cache.pop(oldest_key)
            self.eviction_count += 1
            try:
                from .metrics import increment_cache_eviction
                increment_cache_eviction('memory')
            except:
                pass  # Ignore metrics errors
        self.cache[cache_key] = entry
        try:
            from .metrics import update_cache_size
            update_cache_size(len(self.cache), 'memory')
        except:
            pass  # Ignore metrics errors

    def stats(self):
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "hits": self.hits, 
            "misses": self.misses, 
            "hit_rate": hit_rate,
            "expiry_count": self.expiry_count,
            "eviction_count": self.eviction_count
        }


class TrackedQueueItem:
    """
    Wrapper to track queue waiting time
    """
    def __init__(self, item, mode: str = "simple"):
        self.item = item
        self.enqueue_time = time.time()
        self.mode = mode
        
    def get_waiting_time(self):
        return time.time() - self.enqueue_time


class ModeBasedQueueManager:
    """
    Queue manager that separates queues by processing mode (simple, full, super)
    """
    def __init__(self):
        self.queues = defaultdict(list)  # {mode: [TrackedQueueItem, ...]}
        self.queue_sizes = defaultdict(int)  # {mode: size}
        self.locks = defaultdict(asyncio.Lock)  # {mode: lock}
    
    def add_to_queue(self, item, mode: str = "simple") -> TrackedQueueItem:
        """Add an item to the appropriate queue based on mode"""
        tracked_item = TrackedQueueItem(item, mode)
        self.queues[mode].append(tracked_item)
        self.queue_sizes[mode] += 1
        # Update scaler with the new queue length
        scaler.update_queue_length(self.queue_sizes[mode], mode)
        return tracked_item
    
    def get_from_queue(self, mode: str = "simple") -> Optional[TrackedQueueItem]:
        """Get an item from the specified mode queue"""
        if self.queues[mode]:
            item = self.queues[mode].pop(0)
            self.queue_sizes[mode] -= 1
            # Update scaler with the new queue length
            scaler.update_queue_length(self.queue_sizes[mode], mode)
            return item
        return None
    
    def get_queue_size(self, mode: str = "simple") -> int:
        """Get the size of a specific mode queue"""
        return self.queue_sizes[mode]
    
    def get_all_queue_sizes(self) -> Dict[str, int]:
        """Get all queue sizes by mode"""
        return dict(self.queue_sizes)


class TaskEngine:
    """
    TaskEngine layer: Handle caching, rate limiting, and task orchestration
    Enhanced with auto-throttling, auto-scaling, anomaly detection, and mode-based queue separation
    """
    def __init__(self, 
                 fetcher: PageFetcher,
                 extractor: DataExtractor,
                 redis_cache: Optional[RedisCache] = None,
                 rate_limiter: Optional[RateLimiter] = None,
                 cache_ttl: int = 300):
        
        self.fetcher = fetcher
        self.extractor = extractor
        self.redis_cache = redis_cache
        self.rate_limiter = rate_limiter
        self.cache_ttl = cache_ttl
        
        # Shared in-memory cache
        self.shared_cache = SharedInMemoryCache(max_size=500)
        
        # Mode-based queue management
        self.queue_manager = ModeBasedQueueManager()
        
        # Pure single-flight for in-process coordination
        self.pure_single_flight = PureSingleFlight(timeout=45.0)
        
        # Redis coordination for multi-process coordination - with safe initialization
        try:
            redis_url = "redis://localhost:6379"  # Default, can be overridden
            if self.redis_cache and hasattr(self.redis_cache, 'redis_url'):
                redis_url = self.redis_cache.redis_url
            self.redis_coordination = RedisCoordination(redis_url=redis_url, lock_timeout=30)
        except Exception:
            logger.warning("Failed to initialize Redis coordination, will use in-process single-flight only")
            self.redis_coordination = None  # Fallback to in-process only
        
        # Cache manager for structured caching - with safe initialization
        try:
            self.cache_manager = FacebookCacheManager(
                redis_cache_instance=self.redis_cache,
                local_cache=self.shared_cache,
                cache_ttl=self.cache_ttl
            )
        except Exception:
            logger.error("Failed to initialize FacebookCacheManager", exc_info=True)
            # Create a basic cache manager that at least has the local cache
            self.cache_manager = FacebookCacheManager(
                redis_cache_instance=None,
                local_cache=self.shared_cache,
                cache_ttl=self.cache_ttl
            )
        
        self.stats = {
            "total_requests": 0,
            "cached_requests": 0,
            "successful_scrapes": 0,
            "failed_scrapes": 0,
            "total_time": 0.0
        }

    async def initialize(self):
        """Initialize components that need async setup"""
        if self.redis_coordination:
            try:
                await self.redis_coordination.connect()
            except Exception as e:
                logger.warning(f"Failed to connect Redis coordination: {e}, continuing with in-process single-flight only")
                self.redis_coordination = None  # Disable Redis coordination if connection fails

    async def get_facebook_metadata(self, url: str, mode: str = "simple", 
                                  use_cache: bool = True) -> Dict[str, Any]:
        """
        Clean execution flow:
        1. Cache-first (including negative results)
        2. Redis single-flight (if needed and available)
        3. In-process single-flight (if needed)
        4. Scrape (only by leader)
        5. Fail-fast (no fallback scraping)
        """
        
        self.stats["total_requests"] += 1
        increment_scrape_attempts(mode)

        # Apply throttling delay before processing
        current_delay = throttler.get_current_delay()
        if current_delay > 0:
            await asyncio.sleep(current_delay)

        # Step 1: Check cache first (including negative results)
        if use_cache:
            try:
                cached_result = await self.cache_manager.get_with_negative_cache(url)
                if cached_result:
                    # Update throttler with cache hit
                    throttler.update_cache_stats(cache_hit=True)
                    
                    self.stats["cached_requests"] += 1
                    result = dict(cached_result)  # Copy to avoid reference issues
                    result['from_cache'] = True
                    return result
            except Exception as e:
                logger.error(f"Cache lookup failed: {e}", exc_info=True)
            else:
                # Update throttler with cache miss
                throttler.update_cache_stats(cache_hit=False)

        # Step 2: Redis coordination (cross-process) - only if available
        if self.redis_coordination:
            try:
                redis_result = await self.redis_coordination.execute_with_coordination(
                    url, self._execute_single_flight_scrape, url, mode
                )
                return redis_result
            except TimeoutError:
                # FAIL-FAST: Don't fallback to scraping, return error
                return {
                    "url": url,
                    "error": "Service temporarily unavailable due to high load",
                    "success": False,
                    "error_type": "service_unavailable"
                }
            except Exception as e:
                # For other Redis errors, log and fall back to in-process single-flight
                logger.error(f"Redis coordination error for {url}: {e}")
                # Continue to in-process single-flight instead of returning error
        else:
            logger.debug(f"Redis coordination not available for {url}, using in-process single-flight only")

        # Fallback to in-process single-flight only
        try:
            result = await self.pure_single_flight.do(url, self._perform_scrape, url, mode)
            
            # Leader is responsible for caching result
            if result.get("success"):
                try:
                    await self.cache_manager.store_result(url, result)
                except Exception as e:
                    logger.error(f"Failed to store result in cache: {e}", exc_info=True)
            else:
                # Store negative result
                error_info = {
                    "type": result.get("error_type", "unknown"),
                    "message": result.get("error", "Unknown error")
                }
                try:
                    await self.cache_manager.store_negative_result(url, error_info)
                except Exception as e:
                    logger.error(f"Failed to store negative result in cache: {e}", exc_info=True)
            
            return result
        except Exception as e:
            # Even on exception, return structured error (no fallback scraping)
            error_result = {
                "url": url,
                "error": str(e),
                "success": False,
                "error_type": "scraping_error"
            }
            return error_result

    async def _execute_single_flight_scrape(self, url: str, mode: str) -> Dict[str, Any]:
        """
        Single-flight execution that includes in-process coordination
        """
        # Use pure single-flight for in-process coordination
        async def scrape_fn():
            return await self._perform_scrape(url, mode)
        
        try:
            result = await self.pure_single_flight.do(url, scrape_fn)
            
            # Leader is responsible for caching result
            if result.get("success"):
                try:
                    await self.cache_manager.store_result(url, result)
                except Exception as e:
                    logger.error(f"Failed to store result in cache: {e}", exc_info=True)
            else:
                # Store negative result
                error_info = {
                    "type": result.get("error_type", "unknown"),
                    "message": result.get("error", "Unknown error")
                }
                try:
                    await self.cache_manager.store_negative_result(url, error_info)
                except Exception as e:
                    logger.error(f"Failed to store negative result in cache: {e}", exc_info=True)
            
            return result
        except Exception as e:
            # Even on exception, return structured error (no fallback scraping)
            error_result = {
                "url": url,
                "error": str(e),
                "success": False,
                "error_type": "scraping_error"
            }
            return error_result

    async def _perform_scrape(self, url: str, mode: str = "simple") -> Dict[str, Any]:
        """Execute the actual scraping - only called by leader"""
        # Apply rate limiting
        if self.rate_limiter:
            await self.rate_limiter.acquire()

        # Implement retry mechanism with exponential backoff
        max_retries = 3
        retry_count = 0
        last_exception = None

        while retry_count <= max_retries:
            try:
                start = time.time()
                
                # Get a page and context from pool via fetcher
                page, context = await self.fetcher.browser_pool.get_page()
                
                try:
                    # Fetch page content
                    fetch_result = await self.fetcher.fetch_page_content(page, url, mode)
                    
                    # Update throttler with navigation time
                    throttler.update_navigation_time(fetch_result["navigation_time"], mode)
                    
                    # Extract data
                    extracted_data = await self.extractor.extract_data(fetch_result["page"], mode)
                    
                    # Combine results
                    result = {**fetch_result, **extracted_data}
                    # Remove the page object as it shouldn't be returned to the user
                    if "page" in result:
                        del result["page"]
                    result["success"] = True
                    result["from_cache"] = False
                    result["scrape_time"] = time.time() - start
                    
                    if result and result.get("success"):
                        self.stats["successful_scrapes"] += 1
                        increment_scrape_success(mode)
                        observe_scrape_duration(result["scrape_time"], mode)
                    else:
                        self.stats["failed_scrapes"] += 1
                        # Determine error type for metrics
                        error_type = "unknown"
                        if result.get("error"):
                            error_msg = str(result["error"]).lower()
                            if "rate" in error_msg or "limit" in error_msg:
                                error_type = "rate_limited"
                                try:
                                    from .metrics import increment_rate_limits
                                    throttler.record_rate_limit_event()  # Update throttler
                                    increment_rate_limits()
                                except:
                                    pass  # Ignore metrics errors
                            elif "checkpoint" in error_msg or "restricted" in error_msg:
                                error_type = "checkpoint"
                                try:
                                    from .metrics import increment_checkpoints
                                    increment_checkpoints()
                                except:
                                    pass  # Ignore metrics errors
                            else:
                                error_type = "other_error"
                        try:
                            increment_scrape_failure(error_type, mode)
                        except:
                            pass  # Ignore metrics errors

                    self.stats["total_time"] += result.get("scrape_time", 0)
                    return result
                    
                finally:
                    # Return page to pool with context
                    await self.fetcher.browser_pool.return_page(page, context)

            except Exception as e:
                last_exception = e
                retry_count += 1
                if retry_count <= max_retries:
                    # Exponential backoff: wait 2^retry_count seconds
                    wait_time = 2 ** retry_count
                    logger.warning(f"Retry {retry_count}/{max_retries} for {url} after error: {e}. Waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    # All retries exhausted
                    logger.error(f"All retries exhausted for {url}. Last error: {e}")

        # If we get here, all retries failed
        logger.error(f"get_facebook_metadata error for {url} after {max_retries} retries: {last_exception}")
        self.stats["failed_scrapes"] += 1
        # Determine error type for metrics
        error_msg = str(last_exception).lower()
        if "rate" in error_msg or "limit" in error_msg:
            error_type = "rate_limited"
            try:
                throttler.record_rate_limit_event()  # Update throttler
                increment_rate_limits()
            except:
                pass  # Ignore metrics errors
        elif "checkpoint" in error_msg or "restricted" in error_msg:
            error_type = "checkpoint"
            try:
                increment_checkpoints()
            except:
                pass  # Ignore metrics errors
        else:
            error_type = "exception"
        try:
            increment_scrape_failure(error_type, mode)
        except:
            pass  # Ignore metrics errors
        result = {"url": url, "error": str(last_exception), "success": False, "scrape_time": 0}
        if self.rate_limiter:
            self.rate_limiter.release()
        return result

    async def get_multiple_metadata_streaming(self, urls: List[str], mode: str = "simple", batch_size: int = 25) -> AsyncGenerator[Dict[str, Any], None]:
        """Process URLs in smaller batches within the streaming function for better resource management"""
        unique_urls = list(dict.fromkeys(urls))
        logger.info(f"Processing {len(unique_urls)} URLs in batches of {batch_size} in mode: {mode}")
        
        # Process URLs in smaller batches to prevent overwhelming the system
        for i in range(0, len(unique_urls), batch_size):
            batch = unique_urls[i:i + batch_size]
            
            # Update queue size for this mode
            self.queue_manager.queue_sizes[mode] = len(batch)
            scaler.update_queue_length(len(batch), mode)
            update_queue_size(len(batch))

            async def _process_batch_item(url):
                tracked_item = TrackedQueueItem(url, mode)
                try:
                    # Record waiting time
                    waiting_time = tracked_item.get_waiting_time()
                    observe_queue_waiting_duration(waiting_time, mode)
                    # Add to scaler for auto-scaling decisions
                    scaler.add_queue_wait_time(waiting_time, mode)
                    
                    res = await self.get_facebook_metadata(url, mode=mode)
                except Exception as e:
                    res = {"url": url, "error": str(e), "success": False}
                return url, res

            tasks = [asyncio.create_task(_process_batch_item(u)) for u in batch]

            # Process batch items as they complete
            for coro in asyncio.as_completed(tasks):
                url, res = await coro
                # Update queue size when task completes
                current_size = len([t for t in tasks if not t.done()])
                self.queue_manager.queue_sizes[mode] = current_size
                scaler.update_queue_length(current_size, mode)
                update_queue_size(current_size)
                yield {"url": url, "data": res}

    async def get_multiple_metadata(self, urls: List[str], mode: str = "simple", batch_size: Optional[int] = 25) -> Dict[str, Any]:
        if batch_size is None:
            # Use rate limiter's max concurrent if available
            batch_size = min(self.rate_limiter.max_concurrent if self.rate_limiter else 6, max(1, len(urls)))
        
        results = {}
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} URLs) in mode: {mode}")
            
            # Update queue size for this mode
            self.queue_manager.queue_sizes[mode] = len(batch)
            scaler.update_queue_length(len(batch), mode)
            update_queue_size(len(batch))
            
            async for item in self.get_multiple_metadata_streaming(batch, mode, batch_size):
                results[item['url']] = item['data']
        return results

    def get_cache_stats(self):
        return self.shared_cache.stats()

    def get_engine_stats(self):
        return self.stats
    
    def get_anomaly_status(self):
        """Get current anomaly detection status"""
        return anomaly_detector.get_anomaly_summary()
    
    def get_scaling_status(self):
        """Get current auto-scaling status"""
        return scaler.get_current_status()
    
    def get_queue_status(self):
        """Get current queue status by mode"""
        return {
            'queue_sizes_by_mode': self.queue_manager.get_all_queue_sizes(),
            'total_queue_size': sum(self.queue_manager.get_all_queue_sizes().values())
        }