# -*- coding: utf-8 -*-
import time
import logging
import asyncio
import random
from typing import Optional, Dict, Any
from playwright.async_api import Page

logger = logging.getLogger(__name__)

from .metrics import observe_extraction_duration


class DataExtractor:
    """
    Extractor layer: Handle data extraction based on mode (simple, full, super)
    """
    
    def __init__(self, mode: str = "simple"):
        self.mode = mode

    async def extract_simple(self, page: Page) -> Dict:
        return await page.evaluate("""() => {
            const get = s => document.querySelector(s)?.content || null;
            return {
                title: get('meta[property="og:title"]') || document.title || null,
                description: get('meta[property="og:description"]') || get('meta[name="description"]') || null,
                image: get('meta[property="og:image"]') || null,
                url: get('meta[property="og:url"]') || window.location.href
            };
        }""")

    async def extract_full(self, page: Page) -> Dict:
        return await page.evaluate("""() => {
            const result = {
                title: document.title || null,
                og_data: {},
                twitter_data: {},
                meta_tags: {},
                images: [],
                videos: []
            };
            document.querySelectorAll('meta').forEach(m => {
                const prop = m.getAttribute('property') || m.getAttribute('name');
                const content = m.getAttribute('content');
                if (prop && content) {
                    result.meta_tags[prop] = content;
                    if (prop.startsWith('og:')) result.og_data[prop.substring(3)] = content;
                    else if (prop.startsWith('twitter:')) result.twitter_data[prop.substring(8)] = content;
                }
            });
            document.querySelectorAll('img[src]').forEach(img => {
                try {
                    if (img.src && img.src.startsWith('http')) result.images.push({src: img.src, alt: img.alt || ''});
                } catch(e){}
            });
            document.querySelectorAll('video[src]').forEach(v => {
                try { if (v.src) result.videos.push(v.src); } catch(e){}
            });
            return result;
        }""")

    async def extract_super(self, page: Page) -> Dict:
        """Super mode: full + innerText snippet of main article/content + json-ld"""
        # Inject optimized extraction script for better performance
        extraction_script = """
        () => {
            const result = {
                title: document.title || null,
                og_data: {},
                twitter_data: {},
                meta_tags: {},
                images: [],
                videos: [],
                article_text: null,
                json_ld: []
            };
            
            // Extract metadata
            document.querySelectorAll('meta').forEach(m => {
                const prop = m.getAttribute('property') || m.getAttribute('name');
                const content = m.getAttribute('content');
                if (prop && content) {
                    result.meta_tags[prop] = content;
                    if (prop.startsWith('og:')) result.og_data[prop.substring(3)] = content;
                    else if (prop.startsWith('twitter:')) result.twitter_data[prop.substring(8)] = content;
                }
            });
            
            // Extract images and videos
            document.querySelectorAll('img[src]').forEach(img => {
                try {
                    if (img.src && img.src.startsWith('http')) result.images.push({src: img.src, alt: img.alt || ''});
                } catch(e){}
            });
            document.querySelectorAll('video[src]').forEach(v => {
                try { if (v.src) result.videos.push(v.src); } catch(e){}
            });
            
            // Extract article text with optimized selectors
            const selectors = [
                'article',
                '[role="article"]',
                'div[data-testid="post_message"]',
                'div[data-ad-preview="message"]',
                'div[data-ft]',
                'main'
            ];
            
            for (const s of selectors) {
                const el = document.querySelector(s);
                if (el && el.innerText && el.innerText.trim().length > 20) {
                    result.article_text = el.innerText.trim().substring(0, 2000);
                    break;
                }
            }
            
            if (!result.article_text) {
                // fallback: first paragraph-like text
                const p = document.querySelector('p');
                if (p && p.innerText && p.innerText.trim().length > 20) {
                    result.article_text = p.innerText.trim().substring(0, 2000);
                }
            }
            
            // Extract JSON-LD
            document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                try { result.json_ld.push(JSON.parse(s.textContent)); } catch(e){}
            });
            
            return result;
        }
        """
        
        # Execute the optimized extraction script
        result = await page.evaluate(extraction_script)
        return result

    async def extract_data(self, page: Page, mode: str = None) -> Dict[str, Any]:
        """Extract data based on mode"""
        selected_mode = mode or self.mode
        
        start = time.time()
        
        if selected_mode == "simple":
            meta = await self.extract_simple(page)
        elif selected_mode == "full":
            meta = await self.extract_full(page)
        else:
            meta = await self.extract_super(page)

        if not isinstance(meta, dict):
            meta = {"title": None}

        extraction_time = time.time() - start
        
        # Record extraction time metric
        observe_extraction_duration(extraction_time, selected_mode)
        
        meta["extraction_time"] = extraction_time
        return meta