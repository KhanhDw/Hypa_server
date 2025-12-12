# -*- coding: utf-8 -*-
import time
import logging
import asyncio
import uuid
from typing import Optional, Dict, Any, List, AsyncGenerator
from .scraper_core import AsyncFacebookScraperStreaming
from .rate_limiter import PerWorkerRateLimiter

logger = logging.getLogger(__name__)


class FacebookScraperAPI:
    """Simple job queue wrapper to integrate with FastAPI or any async server."""

    def __init__(self, scraper_config: Dict = None):
        self.scraper_config = scraper_config or {}
        self.active_jobs: Dict[str, Dict] = {}
        self.job_queue: asyncio.Queue = asyncio.Queue()
        self._workers_started = False

    async def start_worker(self, num_workers: int = 2):
        if self._workers_started:
            return
        self._workers_started = True
        for i in range(num_workers):
            asyncio.create_task(self._worker(f"worker-{i}"))

    async def _worker(self, worker_id: str):
        logger.info(f"{worker_id} starting")
        # Each worker keeps its own scraper context to isolate BrowserPool lifecycle
        # Also use per-worker rate limiter for better concurrency
        async with AsyncFacebookScraperStreaming(**self.scraper_config) as scraper:
            # Override the rate limiter to be per-worker for better concurrency
            if scraper.task_engine and scraper.task_engine.rate_limiter:
                scraper.task_engine.rate_limiter = PerWorkerRateLimiter(
                    max_requests_per_minute=self.scraper_config.get('max_requests_per_minute', 30),
                    max_concurrent=self.scraper_config.get('max_concurrent', 6)
                )
                
            while True:
                job_id, job_data = await self.job_queue.get()
                # Handle both old format (just URLs) and new format (dict with urls and mode)
                if isinstance(job_data, dict) and 'urls' in job_data:
                    urls = job_data['urls']
                    mode = job_data.get('mode', 'simple')
                else:
                    urls = job_data
                    mode = 'simple'  # default mode
                
                self.active_jobs[job_id]['status'] = 'running'
                try:
                    results = {}
                    # Use the new batch_size parameter for more efficient processing and pass mode
                    async for item in scraper.get_multiple_metadata_streaming(urls, mode=mode, batch_size=25):
                        results[item['url']] = item['data']
                    self.active_jobs[job_id]['status'] = 'completed'
                    self.active_jobs[job_id]['results'] = results
                    self.active_jobs[job_id]['completed_at'] = time.time()
                except Exception as e:
                    logger.exception("Worker job failed")
                    self.active_jobs[job_id]['status'] = 'failed'
                    self.active_jobs[job_id]['error'] = str(e)
                finally:
                    self.job_queue.task_done()

    async def create_job(self, urls: List[str], chunk_size: int = 25, mode: str = "simple") -> List[str]:
        """Create multiple jobs with smaller chunk sizes for better processing of large batches"""
        job_ids = []
        for i in range(0, len(urls), chunk_size):
            chunk = urls[i:i + chunk_size]
            job_id = str(uuid.uuid4())
            self.active_jobs[job_id] = {
                "id": job_id,
                "urls": chunk,
                "status": "queued",
                "created_at": time.time(),
                "total_urls": len(chunk),
                "mode": mode
            }
            await self.job_queue.put((job_id, {"urls": chunk, "mode": mode}))
            job_ids.append(job_id)
        return job_ids

    def get_job_status(self, job_id: str) -> Dict:
        return self.active_jobs.get(job_id, {"error": "Job not found"})