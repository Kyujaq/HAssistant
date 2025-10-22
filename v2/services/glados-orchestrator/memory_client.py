"""
Memory Client - Async HTTP client for letta-bridge with caching and resilience
Step 2.5: Memory ↔ LLM Integration
"""
import os
import time
import asyncio
import random
import logging
from typing import List, Dict, Optional, Tuple
from collections import OrderedDict

import httpx

logger = logging.getLogger(__name__)

# Configuration from environment
MEM_URL = os.getenv("MEMORY_URL", "http://letta-bridge:8010")
TOP_K = int(os.getenv("MEMORY_TOP_K", "6"))
CACHE_SIZE = int(os.getenv("MEMORY_CACHE_SIZE", "50"))
CONNECT_TIMEOUT = float(os.getenv("MEMORY_CONNECT_TIMEOUT", "2.0"))
READ_TIMEOUT = float(os.getenv("MEMORY_READ_TIMEOUT", "6.0"))


class LRUCache:
    """Simple LRU cache implementation"""

    def __init__(self, maxsize: int = 50):
        self.cache = OrderedDict()
        self.maxsize = maxsize

    def get(self, key):
        if key not in self.cache:
            return None
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        # Evict oldest if over capacity
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

    def clear(self):
        self.cache.clear()

    def __contains__(self, key):
        return key in self.cache

    def __len__(self):
        return len(self.cache)


class MemoryClient:
    async def add_agent_memory(self, agent_id: str, block: dict) -> dict:
        """
        Add a memory block to a Letta agent's archival memory.
        Args:
            agent_id: The Letta agent ID
            block: Dict with memory block data (text, meta, etc.)
        Returns:
            Response dict from Letta
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"http://letta-server:8283/agents/{agent_id}/archival-memory",
                    json=block
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            self._log_error_throttled("add_agent_memory", str(type(e).__name__), str(e))
            return {"error": str(e)}

    async def search_agent_memory(self, agent_id: str, query: str, top_k: int = 6) -> list:
        """
        Search an agent's archival memory blocks via Letta.
        Args:
            agent_id: The Letta agent ID
            query: Search query string
            top_k: Number of results to return
        Returns:
            List of matching memory blocks
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                params = {"q": query, "top_k": top_k}
                response = await client.get(
                    f"http://letta-server:8283/agents/{agent_id}/archival-memory/search",
                    params=params
                )
                response.raise_for_status()
                return response.json().get("results", [])
        except Exception as e:
            self._log_error_throttled("search_agent_memory", str(type(e).__name__), str(e))
            return []
    """
    Async HTTP client for letta-bridge memory service.

    Features:
    - LRU cache for recent queries (60s TTL)
    - Configurable timeouts (connect=2s, read=6s)
    - Single retry with exponential backoff (200-400ms)
    - Fire-and-forget adds (don't block on failures)
    - Cache invalidation on config changes
    - Throttled error logging (1/minute)
    """

    def __init__(
        self,
        base_url: str = MEM_URL,
        connect_timeout: float = CONNECT_TIMEOUT,
        read_timeout: float = READ_TIMEOUT
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=read_timeout,
            pool=connect_timeout + read_timeout
        )
        self.cache = LRUCache(maxsize=CACHE_SIZE)
        self._config_version = 0
        self._error_log_throttle = {}  # error_type -> last_logged_time

    def invalidate_cache(self):
        """Clear cache when config changes (min_score, top_k, etc.)"""
        self.cache.clear()
        self._config_version += 1
        logger.info(f"Memory cache invalidated (v{self._config_version})")

    async def search(
        self,
        query: str,
        turn_id: str,
        top_k: int = TOP_K,
        filter: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search memories with semantic similarity.

        Args:
            query: The search query text
            turn_id: UUID for traceability
            top_k: Maximum number of results to return
            filter: Optional dict with 'kinds' list to filter by memory type

        Returns:
            List of matching memories with scores

        Raises:
            TimeoutError: If search times out
            httpx.HTTPError: If HTTP request fails
        """
        # Build cache key including config version
        cache_key = (query, top_k, str(filter), self._config_version)

        # Check cache first
        if cache_key in self.cache:
            cached_results, timestamp = self.cache.get(cache_key)
            # Cache valid for 60 seconds
            if time.time() - timestamp < 60:
                logger.debug(f"Memory cache hit for query: {query[:50]}")
                return cached_results

        # Fetch from API with retry logic
        try:
            results = await self._search_with_retry(query, turn_id, top_k, filter)
            # Cache the results
            self.cache.put(cache_key, (results, time.time()))
            return results

        except (TimeoutError, httpx.HTTPError) as e:
            # Throttled error logging (once per minute per error type)
            self._log_error_throttled("search", str(type(e).__name__), str(e))
            return []  # Return empty results on error (graceful degradation)

    async def _search_with_retry(
        self,
        query: str,
        turn_id: str,
        top_k: int,
        filter: Optional[Dict]
    ) -> List[Dict]:
        """Internal search with single retry"""
        last_exception = None

        for attempt in range(2):  # Initial attempt + 1 retry
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    payload = {
                        "q": query,
                        "top_k": top_k,
                        "turn_id": turn_id
                    }
                    if filter:
                        payload["filter"] = filter

                    response = await client.post(
                        f"{self.base_url}/memory/search",
                        json=payload
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data.get("results", [])

            except Exception as e:
                last_exception = e
                if attempt == 0:
                    # Backoff before retry (200-400ms)
                    await asyncio.sleep(random.uniform(0.2, 0.4))
                    logger.debug(f"Memory search retry after error: {e}")
                else:
                    raise

        # Should not reach here, but just in case
        raise last_exception

    async def add(
        self,
        text: str,
        turn_id: str,
        role: str,
        ctx_hits: int,
        kind: str,
        source: str = "orchestrator",
        hash_id: Optional[str] = None
    ) -> Dict:
        """
        Add a memory (fire-and-forget pattern).

        This method returns immediately without waiting for the add to complete.
        Errors are logged but don't block the caller.

        Args:
            text: Memory text content
            turn_id: UUID for traceability
            role: 'user' or 'assistant'
            ctx_hits: Number of context hits used
            kind: Memory type (e.g., 'chat_user', 'chat_assistant', 'note')
            source: Source identifier (default: 'orchestrator')
            hash_id: Optional pre-computed hash for deduplication

        Returns:
            Dict with id, hash_id, and deduped flag (or error info on failure)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "text": text,
                    "kind": kind,
                    "source": source,
                    "turn_id": turn_id,
                    "role": role,
                    "meta": {
                        "turn_id": turn_id,
                        "role": role,
                        "ctx_hits": ctx_hits,
                        "ts": time.time()
                    }
                }
                if hash_id:
                    payload["hash_id"] = hash_id

                response = await client.post(
                    f"{self.base_url}/memory/add",
                    json=payload
                )
                response.raise_for_status()
                return response.json()

        except Exception as e:
            self._log_error_throttled("add", str(type(e).__name__), str(e))
            return {"error": str(e), "id": None, "deduped": False}

    async def update_config(self, updates: Dict) -> Dict:
        """
        Update memory configuration.

        Args:
            updates: Dict with config updates (e.g., {"min_score": 0.7})

        Returns:
            Updated config dict
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/config",
                    json=updates
                )
                response.raise_for_status()
                # Invalidate cache when config changes
                if any(k in updates for k in ["min_score", "top_k"]):
                    self.invalidate_cache()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to update memory config: {e}")
            return {}

    async def record_hit(self, used: bool, hits: int) -> Dict:
        """
        Signal to letta-bridge that memory was (or wasn't) used.

        This increments the memory_search_used_total counter for metrics.

        Args:
            used: Whether the retrieved memories were actually used in the response
            hits: Number of memories retrieved

        Returns:
            Response dict
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/stats/hit",
                    json={"used": used, "hits": hits}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.debug(f"Failed to record memory hit: {e}")
            return {}

    def _log_error_throttled(self, operation: str, error_type: str, message: str):
        """Log error with throttling (once per minute per error type)"""
        now = time.time()
        throttle_key = f"{operation}_{error_type}"
        last_logged = self._error_log_throttle.get(throttle_key, 0)

        if now - last_logged > 60:  # 1 minute throttle
            logger.error(f"Memory {operation} failed ({error_type}): {message}")
            self._error_log_throttle[throttle_key] = now

    def get_stats(self) -> Dict:
        """Get client statistics"""
        return {
            "cache_size": len(self.cache),
            "config_version": self._config_version,
            "base_url": self.base_url
        }
