# -*- coding: utf-8 -*-
"""
Utility module for processing large batches of URLs efficiently
"""
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional
from .scraper_api import FacebookScraperAPI


logger = logging.getLogger(__name__)


class LargeBatchProcessor:
    """
    Utility class to handle large batches (500-2000 URLs) efficiently
    using chunking, proper worker scaling, and resource management
    """
    
    def __init__(self, api: FacebookScraperAPI):
        self.api = api
    
    async def process_large_batch(
        self, 
        urls: List[str], 
        chunk_size: int = 25,
        num_workers: int = 8,
        mode: str = "simple"
    ) -> Dict[str, Any]:
        """
        Process a large batch of URLs efficiently using:
        - Chunking into smaller pieces
        - Proper worker configuration
        - Resource management
        """
        # Ensure appropriate number of workers are running
        if not self.api._workers_started:
            # Update scraper config to use efficient settings
            self.api.scraper_config.update({
                'max_contexts': 5,              # Small and light workers
                'max_pages_per_context': 5,     # Efficient resource usage
                'context_reuse_limit': 250,     # Browser rotation every ~250 navigations
                'max_concurrent': 6,            # Reasonable concurrency per worker
                'mode': mode,                   # Fastest mode for bulk scraping
                'cache_ttl': 600,               # 10-minute cache
                'use_browser_pool': True,
                'enable_images': False          # Disable images for better performance
            })
            await self.api.start_worker(num_workers=num_workers)
        
        # Split URLs into smaller chunks
        total_urls = len(urls)
        job_ids = []
        
        for i in range(0, total_urls, chunk_size):
            chunk = urls[i:i + chunk_size]
            # Create chunked jobs with mode
            chunk_job_ids = await self.api.create_job(chunk, chunk_size=chunk_size, mode=mode)
            job_ids.extend(chunk_job_ids)
        
        # Monitor all jobs and collect results
        results = {}
        failed_jobs = []
        start_time = time.time()
        
        logger.info(f"Processing {total_urls} URLs in {len(job_ids)} chunks of {chunk_size} each")
        
        for idx, job_id in enumerate(job_ids):
            while True:
                status = self.api.get_job_status(job_id)
                if status['status'] in ['completed', 'failed']:
                    if status['status'] == 'completed':
                        results.update(status.get('results', {}))
                        logger.info(f"Completed chunk {idx+1}/{len(job_ids)} ({len(status.get('results', {}))} URLs)")
                    else:
                        failed_jobs.append(job_id)
                        logger.error(f"Failed chunk {idx+1}/{len(job_ids)}: {status.get('error', 'Unknown error')}")
                    break
                await asyncio.sleep(0.5)  # Check every 0.5 seconds to be more responsive
        
        processing_time = time.time() - start_time
        
        summary = {
            'total_urls': total_urls,
            'processed_urls': len(results),
            'failed_jobs': len(failed_jobs),
            'total_chunks': len(job_ids),
            'chunk_size': chunk_size,
            'processing_time_seconds': processing_time,
            'urls_per_second': len(results) / processing_time if processing_time > 0 else 0,
            'results': results
        }
        
        logger.info(f"Batch processing completed: {len(results)}/{total_urls} URLs processed successfully in {processing_time:.2f}s")
        
        if failed_jobs:
            logger.warning(f"{len(failed_jobs)} chunks failed processing")
            
        return summary