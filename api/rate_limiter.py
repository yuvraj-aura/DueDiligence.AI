import time
import asyncio
from collections import deque
from typing import Dict, Tuple

class RateLimiter:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        # Implement singleton so the rate limiter is shared across all module threads
        if cls._instance is None:
            cls._instance = super(RateLimiter, cls).__new__(cls)
            cls._instance.reddit_calls = deque()
            cls._instance.ph_calls = deque()
            cls._instance.gh_calls = deque()
            cls._instance.ph_cache = {}  # Cache key: niche_slug, value: (timestamp, count)
        return cls._instance

    async def check_reddit(self):
        """Enforces Reddit rate limits: 60 requests/minute"""
        async with self._lock:
            now = time.time()
            while self.reddit_calls and self.reddit_calls[0] < now - 60:
                self.reddit_calls.popleft()
            
            if len(self.reddit_calls) >= 60:
                wait_time = 60.0 - (now - self.reddit_calls[0])
                print(f"RateLimiter: Reddit limit hit. Throttling request. Sleeping {wait_time:.2f}s...")
                await asyncio.sleep(max(wait_time, 0.1))
                
            self.reddit_calls.append(time.time())

    async def check_github(self):
        """Enforces GitHub rate limits: 5000 requests/hour"""
        async with self._lock:
            now = time.time()
            while self.gh_calls and self.gh_calls[0] < now - 3600:
                self.gh_calls.popleft()
                
            if len(self.gh_calls) >= 5000:
                wait_time = 3600.0 - (now - self.gh_calls[0])
                print(f"RateLimiter: GitHub limit hit. Throttling request. Sleeping {wait_time:.2f}s...")
                await asyncio.sleep(max(wait_time, 0.1))
                
            self.gh_calls.append(time.time())

    async def check_product_hunt(self, query: str) -> Tuple[bool, int]:
        """
        Enforces Product Hunt rate limits: 60 requests/hour.
        Utilizes aggressive local memory caching to avoid calling Product Hunt API repeatedly.
        Returns: (is_cached, cached_value)
        """
        async with self._lock:
            now = time.time()
            
            # Check cache first (1 hour cache TTL)
            if query in self.ph_cache:
                cache_time, count = self.ph_cache[query]
                if now - cache_time < 3600:
                    print(f"RateLimiter: Product Hunt cache HIT for query '{query}'. Returning cached launches: {count}")
                    return True, count

            while self.ph_calls and self.ph_calls[0] < now - 3600:
                self.ph_calls.popleft()
                
            if len(self.ph_calls) >= 60:
                wait_time = 3600.0 - (now - self.ph_calls[0])
                print(f"RateLimiter: Product Hunt limit hit. Throttling request. Sleeping {wait_time:.2f}s...")
                await asyncio.sleep(max(wait_time, 0.1))
                
            self.ph_calls.append(time.time())
            return False, 0

    async def cache_product_hunt(self, query: str, count: int):
        async with self._lock:
            self.ph_cache[query] = (time.time(), count)
