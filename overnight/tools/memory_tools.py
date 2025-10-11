"""
Memory management tools for overnight intelligence system.

Integrates with Letta Bridge for persistent memory operations.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

# Configuration
LETTA_BRIDGE_URL = os.getenv("LETTA_BRIDGE_URL", "http://hassistant-letta-bridge:8081")
LETTA_API_KEY = os.getenv("BRIDGE_API_KEY", "d6DkfuU7zPOpcoeAVabiNNPhTH6TcFrZ")


async def add_memory(
    title: str,
    content: str,
    mem_type: str = "insight",
    tier: str = "medium",
    tags: Optional[List[str]] = None,
    confidence: float = 0.8,
    pin: bool = False
) -> Dict[str, Any]:
    """
    Add a memory to Letta Bridge.
    
    Args:
        title: Memory title
        content: Memory content
        mem_type: Memory type (fact, event, task, preference, insight, etc.)
        tier: Memory tier (short, medium, long, permanent)
        tags: Optional list of tags
        confidence: Confidence score (0.0-1.0)
        pin: Whether to pin the memory
        
    Returns:
        API response with memory ID
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{LETTA_BRIDGE_URL}/memory/add",
                headers={"x-api-key": LETTA_API_KEY},
                json={
                    "type": mem_type,
                    "title": title,
                    "content": content,
                    "tier": tier,
                    "tags": tags or [],
                    "confidence": confidence,
                    "pin": pin,
                    "generate_embedding": True
                }
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Added memory: {title} (ID: {result.get('id')})")
            return result
    except Exception as e:
        logger.error(f"Failed to add memory '{title}': {e}")
        raise


async def search_memories(
    query: str,
    k: int = 10,
    tiers: Optional[List[str]] = None,
    types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Search memories using semantic similarity.
    
    Args:
        query: Search query
        k: Number of results to return
        tiers: Filter by memory tiers
        types: Filter by memory types
        
    Returns:
        List of matching memories
    """
    try:
        params = {"q": query, "k": k}
        if tiers:
            params["tiers"] = ",".join(tiers)
        if types:
            params["types"] = ",".join(types)
            
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{LETTA_BRIDGE_URL}/memory/search",
                headers={"x-api-key": LETTA_API_KEY},
                params=params
            )
            response.raise_for_status()
            results = response.json()
            logger.info(f"Found {len(results)} memories for query: {query}")
            return results
    except Exception as e:
        logger.error(f"Failed to search memories: {e}")
        return []


async def get_daily_brief() -> Dict[str, Any]:
    """
    Get daily brief of important recent memories.
    
    Returns:
        Daily brief with recent memories and insights
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{LETTA_BRIDGE_URL}/daily_brief",
                headers={"x-api-key": LETTA_API_KEY}
            )
            response.raise_for_status()
            brief = response.json()
            logger.info(f"Retrieved daily brief with {len(brief.get('memories', []))} memories")
            return brief
    except Exception as e:
        logger.error(f"Failed to get daily brief: {e}")
        return {}


async def pin_memory(memory_id: str, pin: bool = True) -> Dict[str, Any]:
    """
    Pin or unpin a memory.
    
    Args:
        memory_id: Memory ID to pin/unpin
        pin: True to pin, False to unpin
        
    Returns:
        API response
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{LETTA_BRIDGE_URL}/memory/pin",
                headers={"x-api-key": LETTA_API_KEY},
                json={"id": memory_id, "pin": pin}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"{'Pinned' if pin else 'Unpinned'} memory: {memory_id}")
            return result
    except Exception as e:
        logger.error(f"Failed to pin/unpin memory {memory_id}: {e}")
        raise


async def run_maintenance() -> Dict[str, Any]:
    """
    Run memory maintenance to clean up old memories.
    
    Returns:
        Maintenance results with eviction counts
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{LETTA_BRIDGE_URL}/memory/maintenance",
                headers={"x-api-key": LETTA_API_KEY}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Memory maintenance completed: {result.get('total_evicted', 0)} memories evicted")
            return result
    except Exception as e:
        logger.error(f"Failed to run memory maintenance: {e}")
        raise
