# -*- coding: utf-8 -*-
import time
import logging
import asyncio
import json
import hashlib
from typing import Optional, Dict, Any, List, AsyncGenerator
from collections import OrderedDict

logger = logging.getLogger(__name__)

from .redis_cache import RedisCache
from .rate_limiter import RateLimiter
from .fetcher import PageFetcher
from .extractor import DataExtractor


class SharedInMemoryCache:
    """
    Shared in-memory cache to reduce Redis calls
    """
    def __init__(self, max_size: int = 500):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, url: str) -> Optional[Dict]:
        cache_key = f"fb_scrape:{hashlib.md5(url.encode()).hexdigest()}"
        if cache_key in self.cache:
            self.hits += 1
            # Move to end (most recently used)
            value = self.cache.pop(cache_key)
            self.cache[cache_key] = value
            return value
        self.misses += 1
        return None

    def set(self, url: str, data: Dict):
        cache_key = f"fb_scrape:{hashlib.md5(url.encode()).hexdigest()}"
        # -*- coding: utf-8 -*-
import time
import logging
import asyncio
import json
import hashlib
from typing import Optional, Dict, Any, List, AsyncGenerator
from collections import OrderedDict, defaultdict
import asyncio

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
        cache_key = f"fb_scrape:{hashlib.md5(url.encode()).hexdigest()}"
        if cache_key in self.cache:
            # Check TTL expiry
            entry = self.cache[cache_key]
            if time.time() - entry.get('timestamp', 0) > entry.get('ttl', 600):  # Increase TTL to 10 minutes
                # Entry expired, remove it
                self.cache.pop(cache_key)
                self.expiry_count += 1
                from .metrics import increment_cache_ttl_expiry
                increment_cache_ttl_expiry('memory')
                return None
                
            self.hits += 1
            # Move to end (most recently used)
            value = self.cache.pop(cache_key)
            self.cache[cache_key] = value
            from .metrics import increment_cache_hit
            increment_cache_hit('memory')
            return value
        self.misses += 1
        from .metrics import increment_cache_miss
        increment_cache_miss('memory', 'not_found')
        return None

    def set(self, url: str, data: Dict, ttl: int = 600):  # Increase TTL to 10 minutes
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
            from .metrics import increment_cache_eviction
            increment_cache_eviction('memory')
        self.cache[cache_key] = entry
        from .metrics import update_cache_size
        update_cache_size(len(self.cache), 'memory')

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
        
        self.stats = {
            "total_requests": 0,
            "cached_requests": 0,
            "successful_scrapes": 0,
            "failed_scrapes": 0,
            "total_time": 0.0
        }

    async def get_facebook_metadata(self, url: str, mode: str = "simple", 
                                  use_cache: bool = True) -> Dict[str, Any]:
        """Main method to get facebook metadata with caching, throttling, and rate limiting"""
        self.stats["total_requests"] += 1
        increment_scrape_attempts(mode)

        # Apply throttling delay before processing
        current_delay = throttler.get_current_delay()
        if current_delay > 0:
            await asyncio.sleep(current_delay)

        # Check shared in-memory cache first
        if use_cache:
            cached_data = self.shared_cache.get(url)
            if cached_data:
                # Update throttler with cache hit
                throttler.update_cache_stats(cache_hit=True)
                
                self.stats["cached_requests"] += 1
                result = dict(cached_data['data'])  # Extract just the data part
                result['from_cache'] = True
                return result
            else:
                # Update throttler with cache miss
                throttler.update_cache_stats(cache_hit=False)

        # Check Redis cache
        if use_cache and self.redis_cache:
            try:
                redis_data = await self.redis_cache.get(url)
                if redis_data:
                    self.stats["cached_requests"] += 1
                    redis_data['from_cache'] = True
                    # Add to shared cache
                    self.shared_cache.set(url, redis_data, self.cache_ttl)
                    return redis_data
            except Exception:
                logger.debug("Redis cache get failed", exc_info=True)

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
                        # Cache the result
                        self.shared_cache.set(url, result, self.cache_ttl)
                        if self.redis_cache:
                            try:
                                await self.redis_cache.set(url, result, self.cache_ttl)
                            except Exception:
                                logger.debug("Redis set failed", exc_info=True)
                    else:
                        self.stats["failed_scrapes"] += 1
                        # Determine error type for metrics
                        error_type = "unknown"
                        if result.get("error"):
                            error_msg = str(result["error"]).lower()
                            if "rate" in error_msg or "limit" in error_msg:
                                error_type = "rate_limited"
                                from .metrics import increment_rate_limits
                                throttler.record_rate_limit_event()  # Update throttler
                                increment_rate_limits()
                            elif "checkpoint" in error_msg or "restricted" in error_msg:
                                error_type = "checkpoint"
                                from .metrics import increment_checkpoints
                                increment_checkpoints()
                            else:
                                error_type = "other_error"
                        increment_scrape_failure(error_type, mode)

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
            from .metrics import increment_rate_limits
            throttler.record_rate_limit_event()  # Update throttler
            increment_rate_limits()
        elif "checkpoint" in error_msg or "restricted" in error_msg:
            error_type = "checkpoint"
            from .metrics import increment_checkpoints
            increment_checkpoints()
        else:
            error_type = "exception"
        increment_scrape_failure(error_type, mode)
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
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {"hits": self.hits, "misses": self.misses, "hit_rate": hit_rate}


class TaskEngine:
    """
    TaskEngine layer: Handle caching, rate limiting, and task orchestration
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
        
        self.stats = {
            "total_requests": 0,
            "cached_requests": 0,
            "successful_scrapes": 0,
            "failed_scrapes": 0,
            "total_time": 0.0
        }

    async def get_facebook_metadata(self, url: str, mode: str = "simple", 
                                  use_cache: bool = True) -> Dict[str, Any]:
        """Main method to get facebook metadata with caching and rate limiting"""
        self.stats["total_requests"] += 1

        # Check shared in-memory cache first
        if use_cache:
            cached_data = self.shared_cache.get(url)
            if cached_data:
                self.stats["cached_requests"] += 1
                result = dict(cached_data)
                result['from_cache'] = True
                return result

        # Check Redis cache
        if use_cache and self.redis_cache:
            try:
                redis_data = await self.redis_cache.get(url)
                if redis_data:
                    self.stats["cached_requests"] += 1
                    redis_data['from_cache'] = True
                    # Add to shared cache
                    self.shared_cache.set(url, redis_data)
                    return redis_data
            except Exception:
                logger.debug("Redis cache get failed", exc_info=True)

        # Apply rate limiting
        if self.rate_limiter:
            await self.rate_limiter.acquire()

        try:
            start = time.time()
            
            # Get a page and context from pool via fetcher
            page, context = await self.fetcher.browser_pool.get_page()
            
            try:
                # Fetch page content
                fetch_result = await self.fetcher.fetch_page_content(page, url, mode)
                
                # Extract data
                extracted_data = await self.extractor.extract_data(fetch_result["page"], mode)
                
                # Combine results but exclude the page object from the final result
                result = {**fetch_result, **extracted_data}
                # Remove the page object as it shouldn't be returned to the user
                if "page" in result:
                    del result["page"]
                result["success"] = True
                result["from_cache"] = False
                result["scrape_time"] = time.time() - start
                
                if result and result.get("success"):
                    self.stats["successful_scrapes"] += 1
                    # Cache the result
                    self.shared_cache.set(url, result)
                    if self.redis_cache:
                        try:
                            await self.redis_cache.set(url, result, self.cache_ttl)
                        except Exception:
                            logger.debug("Redis set failed", exc_info=True)
                else:
                    self.stats["failed_scrapes"] += 1

                self.stats["total_time"] += result.get("scrape_time", 0)
                return result
                
            finally:
                # Return page to pool with context
                await self.fetcher.browser_pool.return_page(page, context)

        except Exception as e:
            logger.error(f"get_facebook_metadata error for {url}: {e}")
            self.stats["failed_scrapes"] += 1
            result = {"url": url, "error": str(e), "success": False, "scrape_time": 0}
            return result
        finally:
            if self.rate_limiter:
                self.rate_limiter.release()

    async def get_multiple_metadata_streaming(self, urls: List[str], mode: str = "simple") -> AsyncGenerator[Dict[str, Any], None]:
        """Stream results as they complete (deduped)"""
        unique_urls = list(dict.fromkeys(urls))
        logger.info(f"Scraping {len(unique_urls)} unique URLs (from {len(urls)} input)")

        async def _wrap(url):
            try:
                res = await self.get_facebook_metadata(url, mode=mode)
            except Exception as e:
                res = {"url": url, "error": str(e), "success": False}
            return url, res

        tasks = [asyncio.create_task(_wrap(u)) for u in unique_urls]

        # stream in completion order
        for coro in asyncio.as_completed(tasks):
            url, res = await coro
            yield {"url": url, "data": res}

    async def get_multiple_metadata(self, urls: List[str], mode: str = "simple", batch_size: Optional[int] = None) -> Dict[str, Any]:
        if batch_size is None:
            # Use rate limiter's max concurrent if available
            batch_size = min(self.rate_limiter.max_concurrent if self.rate_limiter else 6, max(1, len(urls)))
        
        results = {}
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} URLs)")
            async for item in self.get_multiple_metadata_streaming(batch, mode):
                results[item['url']] = item['data']
        return results

    def get_cache_stats(self):
        return self.shared_cache.stats()

    def get_engine_stats(self):
        return self.stats