import os
import json
import logging
import asyncio
from typing import Optional, Dict
import redis.asyncio as aioredis
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("session_cache")

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class SessionCache:
    # Class-level shared memory database and lock to ensure singleton behavior
    # when Redis is offline and multiple instances of SessionCache are created.
    _shared_memory_db: Dict[str, str] = {}
    _shared_lock = asyncio.Lock()
    
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self._redis_failed = False
        self._initialized = False

    async def initialize(self):
        """
        Non-blocking cache initialization. Attempts to connect to Redis
        without blocking active user requests on startup.
        """
        if self._initialized:
            return
        
        try:
            logger.info(f"SessionCache: Pre-checking Redis connection at {REDIS_URL}...")
            client = aioredis.from_url(REDIS_URL, decode_responses=True)
            # Test connection with a short ping timeout
            await asyncio.wait_for(client.ping(), timeout=0.5)
            self.redis_client = client
            logger.info("SessionCache: Successfully connected to Redis.")
        except Exception as e:
            logger.warning(f"SessionCache: Redis offline ({e}). Using in-memory fallback cache.")
            self._redis_failed = True
            self.redis_client = None
            
        self._initialized = True

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        # Never block active requests. If not initialized yet, return None to fallback to memory.
        if not self._initialized or self._redis_failed:
            return None
            
        return self.redis_client

    async def set_session(self, session_id: str, data: dict, ttl: int = 86400) -> bool:
        """
        Store session data. Serializes dictionary data to JSON.
        """
        serialized = json.dumps(data)
        client = await self._get_redis()
        
        if client:
            try:
                await client.set(session_id, serialized, ex=ttl)
                return True
            except Exception as e:
                logger.warning(f"Redis write error: {e}. Falling back to in-memory store for session {session_id}.")
        
        async with self._shared_lock:
            self._shared_memory_db[session_id] = serialized
        return True

    async def get_session(self, session_id: str) -> Optional[dict]:
        """
        Retrieve session data. Deserializes JSON string back to dictionary.
        """
        client = await self._get_redis()
        
        if client:
            try:
                serialized = await client.get(session_id)
                if serialized:
                    return json.loads(serialized)
                return None
            except Exception as e:
                logger.warning(f"Redis read error: {e}. Falling back to in-memory store for read.")

        async with self._shared_lock:
            serialized = self._shared_memory_db.get(session_id)
            if serialized:
                return json.loads(serialized)
            return None
