"""
GLaDOS Orchestrator v2.2 - Unified Voice Architecture

Combines three architectural patterns:
1. Tool Provider: Provides specialized tools for Ollama LLM function calling
2. Smart Routing: Intelligently routes queries between models for optimal performance
3. Personality Handoff: Ensures consistent GLaDOS voice across all responses

Architecture:
- Home Assistant connects to this orchestrator
- Transparent pass-through for model management (/api/tags, /api/pull, etc.)
- Smart routing for chat (/api/chat):
  * Simple queries → glados-hermes3 (direct, fast path)
  * Complex queries → qwen3:4b (background analysis) → glados-hermes3 (GLaDOS voice)
- Tools accessible via /tool/* endpoints

Features:
- RESTful tool endpoints for LLM function calling
- Complexity-based model routing with personality preservation
- Qwen analyzes complex queries in background, Hermes presents results in character
- Integrates with Letta Bridge for persistent memory
- Streaming support for both simple and complex queries
- Debug logging for troubleshooting
- Vision analysis via Qwen2.5-VL (GPU-accelerated)

Build: 2025-10-10T01:45
"""

import re
import os
import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

import httpx
import redis
import imagehash
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, HTTPException, Request, Header, Body
from fastapi.responses import StreamingResponse, Response, PlainTextResponse
from pydantic import BaseModel, Field

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("glados-orchestrator")

def log_structured(event: str, **kwargs):
    """
    Emit structured log in JSON format for observability.

    Args:
        event: Event name (e.g., "screen_analysis_start")
        **kwargs: Additional fields (session_id, region, frame_sig, latency_ms, etc.)
    """
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "event": event,
        **kwargs
    }
    logger.info(json.dumps(log_data))

# Configuration
LETTA_BRIDGE_URL = os.getenv("LETTA_BRIDGE_URL", "http://hassistant-letta-bridge:8081")
LETTA_API_KEY = os.getenv("LETTA_API_KEY", "d6DkfuU7zPOpcoeAVabiNNPhTH6TcFrZ")
PORT = int(os.getenv("PORT", "8082"))

# Kitchen, Overnight, and Vision API configuration
KITCHEN_API_URL = os.getenv("KITCHEN_API_URL", "http://hassistant-kitchen-api:8083")
OVERNIGHT_API_URL = os.getenv("OVERNIGHT_API_URL", "http://hassistant-overnight:8084")
VISION_GATEWAY_URL = os.getenv("VISION_GATEWAY_URL", "http://vision-gateway:8088")

# Ollama configuration for routing
OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://ollama-chat:11434")
OLLAMA_VISION_URL = os.getenv("OLLAMA_VISION_URL", "http://ollama-vision:11434")
HERMES_MODEL = os.getenv("HERMES_MODEL", "glados-hermes3")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen2.5vl:7b")

# Redis configuration for screen analysis caching
REDIS_HOST = os.getenv("REDIS_HOST", "hassistant-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
SCREEN_CACHE_TTL = int(os.getenv("SCREEN_CACHE_TTL", "60"))  # seconds

# Initialize Redis client
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD if REDIS_PASSWORD else None,
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
    logger.info(f"✅ Redis connected at {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.warning(f"⚠️  Redis connection failed: {e}. Caching disabled.")
    redis_client = None

# Prometheus metrics
screen_analysis_requests = Counter(
    'screen_analysis_requests_total',
    'Total screen analysis requests',
    ['region', 'source']  # labels: region (full/top_left/etc), source (cache/fresh)
)

screen_analysis_latency = Histogram(
    'screen_analysis_latency_ms',
    'Screen analysis latency in milliseconds',
    ['region', 'source'],
    buckets=[10, 50, 100, 500, 1000, 5000, 10000, 20000]  # ms buckets
)

cache_hit_total = Counter(
    'screen_analysis_cache_hits_total',
    'Total cache hits',
    ['region', 'match_type']  # match_type: exact or similar
)

app = FastAPI(
    title="GLaDOS Orchestrator - Unified Voice Architecture",
    version="2.2.0",
    description="Tool endpoints, intelligent routing, and personality-consistent responses for Ollama LLM"
)

# Pydantic models for tool requests/responses
class ToolResponse(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None

class LettaQueryRequest(BaseModel):
    query: str
    limit: int = 5

class AddToGroceryListRequest(BaseModel):
    item: str
    quantity: Optional[int] = None
    notes: Optional[str] = None


class AddInventoryItemRequest(BaseModel):
    name: str
    unit: str
    category: Optional[str] = None
    brand: Optional[str] = None
    calories_per_unit: Optional[float] = None
    protein_per_unit: Optional[float] = None
    carbs_per_unit: Optional[float] = None
    fat_per_unit: Optional[float] = None
    quantity: Optional[float] = None
    purchase_date: Optional[str] = None
    expiration_date: Optional[str] = None
    location: Optional[str] = None
    cost: Optional[float] = None
    notes: Optional[str] = None
    item_id: Optional[int] = None

class HASkillRequest(BaseModel):
    skill_name: str
    parameters: Dict[str, Any] = {}

class QueryComplexity(Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"

# Tool definitions for Ollama function calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current date and time",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "letta_query",
            "description": "Query the Letta memory system for relevant past information and context",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant memories"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of memories to retrieve (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_ha_skill",
            "description": "Execute a Home Assistant skill or automation",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill to execute"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Parameters for the skill",
                        "default": {}
                    }
                },
                "required": ["skill_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_grocery_list",
            "description": "Add an item to the grocery list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "The item to add."},
                    "quantity": {"type": "integer", "description": "Optional quantity metadata (not sent to Paprika)."},
                    "notes": {"type": "string", "description": "Optional metadata for local use."}
                },
                "required": ["item"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_grocery_list",
            "description": "Get the current grocery list.",
            "parameters": { "type": "object", "properties": {} }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recipes",
            "description": "Get recipes from Paprika, optionally filtering by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Filter recipes by name."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory",
            "description": "Get the current inventory.",
            "parameters": { "type": "object", "properties": {} }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_inventory_item",
            "description": "Ensure an item exists in the catalog and optionally log a newly purchased batch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Item name."},
                    "unit": {"type": "string", "description": "Unit of measure (e.g. kg, units, oz)."},
                    "category": {"type": "string", "description": "Inventory category (e.g. produce, dairy). Defaults to 'uncategorized' if omitted."},
                    "brand": {"type": "string", "description": "Optional brand name."},
                    "calories_per_unit": {"type": "number", "description": "Calories per unit if known."},
                    "protein_per_unit": {"type": "number", "description": "Protein grams per unit."},
                    "carbs_per_unit": {"type": "number", "description": "Carbs grams per unit."},
                    "fat_per_unit": {"type": "number", "description": "Fat grams per unit."},
                    "quantity": {"type": "number", "description": "Quantity purchased for the current batch."},
                    "purchase_date": {"type": "string", "description": "Purchase date in YYYY-MM-DD format.", "format": "date"},
                    "expiration_date": {"type": "string", "description": "Optional expiry date in YYYY-MM-DD format.", "format": "date"},
                    "location": {"type": "string", "description": "Storage location (pantry, fridge, etc.)."},
                    "cost": {"type": "number", "description": "Optional purchase cost."},
                    "notes": {"type": "string", "description": "Freeform notes for the batch."},
                    "item_id": {"type": "integer", "description": "Existing item_id to reuse instead of creating one."}
                },
                "required": ["name", "unit"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_overnight_cycle",
            "description": "Manually start the overnight crew cycle for kitchen analysis.",
            "parameters": { "type": "object", "properties": {} }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_overnight_cycle_status",
            "description": "Get the status of the current or last overnight crew cycle.",
            "parameters": { "type": "object", "properties": {} }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_screen",
            "description": "Analyze what's currently visible on the HDMI-connected screen using vision AI. Use this when the user asks about what's on their screen, monitor, or display. Supports analyzing specific screen regions for faster response (e.g., 'top right corner' → region='top_right').",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Optional custom prompt for the vision model. If not provided, will describe what's on screen. Examples: 'What application is open?', 'Is there an error message?', 'What tab is active?'"
                    },
                    "region": {
                        "type": "string",
                        "enum": ["full", "top_left", "top_right", "bottom_left", "bottom_right", "top", "bottom", "left", "right", "center"],
                        "default": "full",
                        "description": "Which part of screen to analyze. If user says 'top left' or 'upper left', use 'top_left'. If 'top right' or 'notification', use 'top_right'. If 'bottom left', use 'bottom_left'. If 'bottom right' or 'clock', use 'bottom_right'. If 'taskbar', use 'bottom'. If no location mentioned, use 'full'."
                    }
                },
                "required": []
            }
        }
    }
]

# Tool acknowledgements for immediate user feedback (reduce perceived latency)
TOOL_ACKNOWLEDGEMENTS = {
    "analyze_screen": "One moment, analyzing your screen...",
    "letta_query": "Let me search my memory...",
    "add_inventory_item": "Adding that to inventory...",
    "add_to_grocery_list": "Adding that to the grocery list...",
    "get_time": "Checking the time...",
    "start_overnight_cycle": "Starting the overnight crew...",
}

# Helper functions for cache management

def detect_tense(query: str) -> str:
    """
    Detect verb tense in query to determine cache strategy.

    Returns:
        "past" - User asking about previous observation (strong cache preference)
        "present" - User asking about current state (prefer live, accept fresh cache)
        "unknown" - Cannot determine tense
    """
    query_lower = query.lower()

    # Past tense indicators
    past_patterns = [
        r'\bwas\b', r'\bwere\b', r'\bhad\b', r'\bdid\b',
        r'\bsaw\b', r'\bshowed\b', r'\bsaid\b', r'\btold\b'
    ]

    # Present tense indicators
    present_patterns = [
        r'\bis\b', r'\bare\b', r'\bhave\b', r'\bhas\b', r'\bdo\b', r'\bdoes\b',
        r'\bsee\b', r'\bshow\b', r'\bsay\b', r'\btell\b'
    ]

    past_count = sum(1 for pattern in past_patterns if re.search(pattern, query_lower))
    present_count = sum(1 for pattern in present_patterns if re.search(pattern, query_lower))

    if past_count > present_count:
        return "past"
    elif present_count > past_count:
        return "present"
    else:
        return "unknown"

def should_use_cache(query: str, cache_data: Optional[Dict], region: str = "full") -> bool:
    """
    Determine if cached screen analysis should be used based on query and cache state.

    Args:
        query: User's query text
        cache_data: Cached analysis data (None if no cache)
        region: Screen region being queried

    Returns:
        True if cache should be used, False if fresh analysis needed
    """
    if not cache_data:
        return False  # No cache available

    # Check if regions match
    if cache_data.get("region", "full") != region:
        return False  # Different region requested

    # Check cache age
    cache_age = datetime.now().timestamp() - cache_data.get("timestamp", 0)
    if cache_age > SCREEN_CACHE_TTL:
        return False  # Cache expired

    query_lower = query.lower()

    # Explicit invalidation phrases - force fresh analysis
    invalidation_phrases = ["look again", "check again", "refresh", "check now", "look now"]
    if any(phrase in query_lower for phrase in invalidation_phrases):
        logger.info(f"🔄 Cache invalidation phrase detected: forcing fresh analysis")
        return False

    # Follow-up indicators - strong cache preference
    followup_phrases = ["any", "also", "tell me more", "what about", "and"]
    has_followup = any(phrase in query_lower for phrase in followup_phrases)

    # Tense detection
    tense = detect_tense(query)

    # Decision logic
    if tense == "past":
        # Past tense = asking about previous observation, use cache if available
        logger.info(f"📖 Past tense detected: using cached analysis")
        return True
    elif tense == "present" and cache_age < 30:
        # Present tense with fresh cache (<30s) = acceptable
        logger.info(f"🕐 Present tense with fresh cache ({cache_age:.1f}s): using cache")
        return True
    elif has_followup:
        # Follow-up question = likely referring to same screen state
        logger.info(f"💬 Follow-up phrase detected: using cached analysis")
        return True
    else:
        # Default: prefer fresh analysis
        logger.info(f"🔍 No cache indicators: performing fresh analysis")
        return False

# Complexity detection patterns (from POC)
SIMPLE_PATTERNS = [
    re.compile(r'\b(turn|set|dim|brighten|switch)\s+(on|off)\b', re.IGNORECASE),
    re.compile(r'\b(what|tell|give|show)\b', re.IGNORECASE),
    re.compile(r'\b(open|close|lock|unlock)\b', re.IGNORECASE),
    re.compile(r'\b(play|pause|stop|skip|next|previous)\b', re.IGNORECASE),
    re.compile(r'\b(hello|hi|hey|good morning|good evening)\b', re.IGNORECASE),
    re.compile(r'\b(how are you|how\'s it going|what\'s up)\b', re.IGNORECASE),
    re.compile(r'\b(thank|thanks|please)\b', re.IGNORECASE),
]

COMPLEX_PATTERNS = [
    re.compile(r'\b(plan|schedule|organize|arrange)\s+(my|a|the)\b', re.IGNORECASE),
    re.compile(r'\b(calendar|appointment|meeting)\s+(on|at|for|tomorrow|next)\b', re.IGNORECASE),
    re.compile(r'\b(if.*then|when.*then)\b', re.IGNORECASE),
    re.compile(r'\b(compare|analyze|explain|why|how does)\b', re.IGNORECASE),
]

def detect_complexity(query: str) -> QueryComplexity:
    """Determine if query is simple or complex"""
    query_lower = query.lower()
    word_count = len(query_lower.split())

    logger.debug(f"Analyzing query: '{query}' ({word_count} words)")

    # Check for complex patterns first
    for pattern in COMPLEX_PATTERNS:
        if pattern.search(query_lower):
            logger.info(f"✓ COMPLEX pattern matched: {pattern.pattern}")
            return QueryComplexity.COMPLEX

    # Check for simple patterns
    for pattern in SIMPLE_PATTERNS:
        if pattern.search(query_lower):
            logger.info(f"✓ SIMPLE pattern matched: {pattern.pattern}")
            return QueryComplexity.SIMPLE

    # Word count heuristic
    if word_count <= 10:
        logger.info(f"✓ SIMPLE (≤10 words)")
        return QueryComplexity.SIMPLE
    elif word_count > 15:
        logger.info(f"✓ COMPLEX (>15 words)")
        return QueryComplexity.COMPLEX

    # Default: SIMPLE
    logger.info(f"✓ SIMPLE (default)")
    return QueryComplexity.SIMPLE

# Helper functions for memory integration
async def retrieve_memory(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieve relevant memories from Letta Bridge"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{LETTA_BRIDGE_URL}/memory/search",
                params={"q": query, "k": limit},
                headers={"x-api-key": LETTA_API_KEY}
            )
            response.raise_for_status()
            memories = response.json()  # Returns list directly
            logger.info(f"Retrieved {len(memories)} memories for query: {query[:50]}...")
            return memories
    except Exception as e:
        logger.warning(f"Failed to retrieve memories: {e}")
        return []

async def save_memory(title: str, content: str, tier: str = "short"):
    """Save interaction to Letta Bridge memory"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{LETTA_BRIDGE_URL}/memory/add",
                json={
                    "type": "conversation",
                    "title": title,
                    "content": content,
                    "tier": tier,
                    "tags": ["assistant", "conversation"],
                    "confidence": 0.8,
                    "generate_embedding": True
                },
                headers={"x-api-key": LETTA_API_KEY}
            )
            logger.debug(f"Saved memory: {title}")
    except Exception as e:
        logger.warning(f"Failed to save memory: {e}")

# Tool Endpoints

@app.get("/tool/list")
async def list_tools():
    """List all available tools in Ollama function calling format"""
    return {
        "tools": TOOL_DEFINITIONS,
        "version": "2.2.0",
        "description": "GLaDOS Orchestrator Tool Provider"
    }

@app.get("/tool/get_time")
@app.post("/tool/get_time")
async def get_time():
    """Get the current date and time"""
    try:
        now = datetime.now()
        result = {
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "formatted": now.strftime("%A, %B %d, %Y at %I:%M %p")
        }
        logger.info(f"get_time called: {result['formatted']}")
        return ToolResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in get_time: {str(e)}")
        return ToolResponse(success=False, error=str(e))

@app.post("/tool/letta_query")
async def letta_query(request: LettaQueryRequest):
    """Query the Letta memory system for relevant information"""
    try:
        logger.info(f"letta_query called with query: {request.query}")
        memories = await retrieve_memory(request.query, request.limit)

        result = {
            "query": request.query,
            "count": len(memories),
            "memories": []
        }

        for mem in memories:
            result["memories"].append({
                "title": mem.get("title", ""),
                "content": mem.get("content", ""),
                "tier": mem.get("tier", ""),
                "created_at": mem.get("created_at", ""),
                "score": mem.get("score", 0.0)
            })

        return ToolResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in letta_query: {str(e)}")
        return ToolResponse(success=False, error=str(e))

@app.post("/tool/execute_ha_skill")
async def execute_ha_skill(request: HASkillRequest):
    """Execute a Home Assistant skill or automation"""
    try:
        logger.info(f"execute_ha_skill called: {request.skill_name} with params: {request.parameters}")

        # Placeholder for HA skill execution
        # In production, this would integrate with Home Assistant's service API
        result = {
            "skill_name": request.skill_name,
            "parameters": request.parameters,
            "status": "placeholder",
            "message": "HA skill execution not yet implemented. This endpoint is ready for integration."
        }

        return ToolResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in execute_ha_skill: {str(e)}")
        return ToolResponse(success=False, error=str(e))

# Kitchen API Tool Endpoints

@app.post("/tool/add_to_grocery_list")
async def add_to_grocery_list(request: AddToGroceryListRequest):
    """Add an item to the grocery list via kitchen-api."""
    try:
        logger.info(f"add_to_grocery_list called with item: {request.item}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{KITCHEN_API_URL}/grocery-list",
                json={"item_name": request.item}
            )
            response.raise_for_status()
            data = response.json()
            metadata: Dict[str, Any] = {}
            if request.quantity is not None:
                metadata["quantity"] = request.quantity
            if request.notes:
                metadata["notes"] = request.notes
            if metadata:
                data["metadata"] = metadata
            return ToolResponse(success=True, data=data)
    except Exception as e:
        logger.error(f"Error in add_to_grocery_list: {str(e)}")
        return ToolResponse(success=False, error=str(e))

@app.get("/tool/get_grocery_list")
@app.post("/tool/get_grocery_list")
async def get_grocery_list():
    """Get the grocery list from kitchen-api."""
    try:
        logger.info("get_grocery_list called")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{KITCHEN_API_URL}/grocery-list")
            response.raise_for_status()
            return ToolResponse(success=True, data=response.json())
    except Exception as e:
        logger.error(f"Error in get_grocery_list: {str(e)}")
        return ToolResponse(success=False, error=str(e))

@app.get("/tool/get_recipes")
@app.post("/tool/get_recipes")
async def get_recipes(name: Optional[str] = None):
    """Get recipes from kitchen-api."""
    try:
        logger.info(f"get_recipes called with name: {name}")
        params = {"name": name} if name else {}
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{KITCHEN_API_URL}/recipes", params=params)
            response.raise_for_status()
            return ToolResponse(success=True, data=response.json())
    except Exception as e:
        logger.error(f"Error in get_recipes: {str(e)}")
        return ToolResponse(success=False, error=str(e))

@app.get("/tool/get_inventory")
@app.post("/tool/get_inventory")
async def get_inventory():
    """Get inventory from kitchen-api."""
    try:
        logger.info("get_inventory called")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{KITCHEN_API_URL}/inventory/items")
            response.raise_for_status()
            return ToolResponse(success=True, data=response.json())
    except Exception as e:
        logger.error(f"Error in get_inventory: {str(e)}")
        return ToolResponse(success=False, error=str(e))

@app.post("/tool/add_inventory_item")
async def add_inventory_item(request: AddInventoryItemRequest):
    """Add an item to the catalog and optionally create a new batch via kitchen-api."""
    try:
        logger.info(f"add_inventory_item called with item: {request.name}")
        async with httpx.AsyncClient() as client:
            item_id = request.item_id
            item_created = False
            matched_item: Optional[Dict[str, Any]] = None

            # Try to reuse an existing item_id based on name/brand when none provided.
            if item_id is None:
                try:
                    lookup_resp = await client.get(f"{KITCHEN_API_URL}/inventory/items")
                    lookup_resp.raise_for_status()
                    for item in lookup_resp.json():
                        name_matches = item.get("name", "").strip().lower() == request.name.strip().lower()
                        brand_matches = True
                        if request.brand is not None:
                            brand_matches = (item.get("brand") or "").strip().lower() == request.brand.strip().lower()
                        if name_matches and brand_matches:
                            item_id = item.get("item_id")
                            matched_item = item
                            break
                except Exception as lookup_error:
                    logger.warning(f"Unable to check existing inventory items: {lookup_error}")

            category_to_use = request.category
            if matched_item:
                category_to_use = category_to_use or matched_item.get("category")
            if category_to_use is None or not str(category_to_use).strip():
                category_to_use = "uncategorized"

            if item_id is None:
                item_payload: Dict[str, Any] = {
                    "name": request.name,
                    "category": category_to_use,
                    "unit": request.unit,
                    "brand": request.brand,
                    "calories_per_unit": request.calories_per_unit,
                    "protein_per_unit": request.protein_per_unit,
                    "carbs_per_unit": request.carbs_per_unit,
                    "fat_per_unit": request.fat_per_unit,
                }
                item_payload = {k: v for k, v in item_payload.items() if v is not None}

                item_resp = await client.post(
                    f"{KITCHEN_API_URL}/inventory/items",
                    json=item_payload,
                )
                item_resp.raise_for_status()
                item_created = True
                item_id = item_resp.json().get("item_id")

            if item_id is None:
                raise RuntimeError("Unable to resolve item_id for inventory item creation.")

            result: Dict[str, Any] = {
                "item_id": item_id,
                "item_created": item_created,
                "category_used": category_to_use,
            }

            if request.quantity is not None:
                purchase_date = request.purchase_date or datetime.now().date().isoformat()
                batch_payload: Dict[str, Any] = {
                    "item_id": item_id,
                    "quantity": request.quantity,
                    "purchase_date": purchase_date,
                }

                optional_fields = {
                    "expiration_date": request.expiration_date,
                    "location": request.location,
                    "cost": request.cost,
                    "notes": request.notes,
                }
                for key, value in optional_fields.items():
                    if value is not None:
                        batch_payload[key] = value

                batch_resp = await client.post(
                    f"{KITCHEN_API_URL}/inventory/batches",
                    json=batch_payload,
                )
                batch_resp.raise_for_status()
                batch_data = batch_resp.json()
                result["batch_id"] = batch_data.get("batch_id")
                result["batch_created"] = True
                result["batch_payload"] = batch_payload
            else:
                result["batch_created"] = False

            return ToolResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in add_inventory_item: {str(e)}")
        return ToolResponse(success=False, error=str(e))

# Overnight API Tool Endpoints

@app.post("/tool/start_overnight_cycle")
async def start_overnight_cycle():
    """Manually start the overnight cycle via overnight-api."""
    try:
        logger.info("start_overnight_cycle called")
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{OVERNIGHT_API_URL}/run-cycle")
            response.raise_for_status()
            return ToolResponse(success=True, data=response.json())
    except Exception as e:
        logger.error(f"Error in start_overnight_cycle: {str(e)}")
        return ToolResponse(success=False, error=str(e))

@app.get("/tool/get_overnight_cycle_status")
@app.post("/tool/get_overnight_cycle_status")
async def get_overnight_cycle_status():
    """Get the status of the overnight cycle from overnight-api."""
    try:
        logger.info("get_overnight_cycle_status called")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OVERNIGHT_API_URL}/status")
            response.raise_for_status()
            return ToolResponse(success=True, data=response.json())
    except Exception as e:
        logger.error(f"Error in get_overnight_cycle_status: {str(e)}")
        return ToolResponse(success=False, error=str(e))

# Vision API Tool Endpoints

class AnalyzeScreenRequest(BaseModel):
    prompt: Optional[str] = None
    region: str = "full"
    query: Optional[str] = None  # Original user query for tense detection
    session_id: Optional[str] = None  # Session/conversation ID for cache isolation

@app.post("/tool/analyze_screen")
async def analyze_screen(request: AnalyzeScreenRequest = Body(default=AnalyzeScreenRequest())):
    """
    Analyze what's on the HDMI-connected screen using Qwen2.5-VL vision AI.
    Supports Redis caching and region-based analysis for faster response.
    """
    try:
        # Extract parameters
        prompt = request.prompt or "Describe what you see on the screen in detail."
        region = request.region or "full"
        query = request.query or prompt  # Fall back to prompt for tense detection
        session_id = request.session_id or "default"

        # Track start time for latency measurement
        start_time = datetime.now()

        logger.info(f"analyze_screen called: prompt='{prompt}', region='{region}', session='{session_id}'")
        log_structured("screen_analysis_start", session_id=session_id, region=region, prompt_length=len(prompt))

        # Step 1: Get current frame signature (lightweight, <100ms)
        current_frame_sig = None
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                peek_response = await client.post(
                    f"{VISION_GATEWAY_URL}/api/peek_frame",
                    json={"region": region}
                )
                peek_result = peek_response.json()
                if peek_result.get("success"):
                    current_frame_sig = peek_result.get("frame_sig")
                    logger.info(f"Current frame signature: {current_frame_sig[:12]}...")
            except Exception as e:
                logger.warning(f"Failed to get frame signature: {e}")

        # Step 2: Check cache using pHash-based key
        cache_data = None
        use_cache = False

        if redis_client and current_frame_sig:
            try:
                # Check if we already have analysis for this exact frame
                cache_key = f"screen:{session_id}:{region}:{current_frame_sig}"
                cached_json = redis_client.get(cache_key)

                if cached_json:
                    cache_data = json.loads(cached_json)
                    # Exact frame match - use tense/query to decide if cache is appropriate
                    use_cache = should_use_cache(query, cache_data, region)

                    if use_cache:
                        logger.info(f"✅ Exact frame match - using cached analysis")
                        log_structured("screen_analysis_cache_hit",
                                     session_id=session_id,
                                     region=region,
                                     frame_sig=current_frame_sig,
                                     match_type="exact")
                        cache_hit_total.labels(region=region, match_type="exact").inc()
                    else:
                        logger.info(f"📊 Exact frame match but query suggests fresh analysis")
                else:
                    # No exact match - check if visually similar to last seen
                    last_seen_key = f"last_seen:{session_id}:{region}"
                    last_frame_sig = redis_client.get(last_seen_key)

                    if last_frame_sig and last_frame_sig != current_frame_sig:
                        # Compute Hamming distance
                        current_hash = imagehash.hex_to_hash(current_frame_sig)
                        last_hash = imagehash.hex_to_hash(last_frame_sig)
                        hamming_dist = current_hash - last_hash

                        logger.info(f"Hamming distance from last frame: {hamming_dist}")

                        # If visually similar (<10 bits changed), consider using old cache
                        if hamming_dist < 10:
                            old_cache_key = f"screen:{session_id}:{region}:{last_frame_sig}"
                            old_cached_json = redis_client.get(old_cache_key)

                            if old_cached_json:
                                cache_data = json.loads(cached_json)
                                use_cache = should_use_cache(query, cache_data, region)

                                if use_cache:
                                    logger.info(f"✅ Similar frame (Hamming: {hamming_dist}) - using cached analysis")
                                    log_structured("screen_analysis_cache_hit",
                                                 session_id=session_id,
                                                 region=region,
                                                 frame_sig=current_frame_sig,
                                                 last_frame_sig=last_frame_sig,
                                                 hamming_distance=hamming_dist,
                                                 match_type="similar")
                                    cache_hit_total.labels(region=region, match_type="similar").inc()
                        else:
                            logger.info(f"🔄 Content changed significantly (Hamming: {hamming_dist})")

            except Exception as e:
                logger.warning(f"Cache check error: {e}")

        if use_cache and cache_data:
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            log_structured("screen_analysis_complete",
                         session_id=session_id,
                         region=region,
                         frame_sig=current_frame_sig,
                         source="cache",
                         latency_ms=round(latency_ms, 2))

            # Record metrics
            screen_analysis_requests.labels(region=region, source="cache").inc()
            screen_analysis_latency.labels(region=region, source="cache").observe(latency_ms)

            return ToolResponse(
                success=True,
                data={
                    **cache_data,
                    "cached": True,
                    "source": "cache",
                    "latency_ms": round(latency_ms, 2)
                }
            )

        # Step 3: Cache miss - perform fresh analysis
        logger.info(f"🔍 Performing fresh vision analysis (region: {region})")

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Call vision-gateway with full prompt
            response = await client.post(
                f"{VISION_GATEWAY_URL}/api/analyze_screen",
                json={"prompt": prompt, "region": region}
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                frame_sig = result.get("frame_sig", current_frame_sig or "unknown")

                analysis_data = {
                    "analysis": result.get("analysis"),
                    "timestamp": datetime.now().timestamp(),
                    "model": result.get("model"),
                    "region": region,
                    "frame_sig": frame_sig,
                    "cached": False,
                    "source": "fresh"
                }

                # Store in Redis cache with pHash-based key
                if redis_client and frame_sig:
                    try:
                        # Primary cache key: screen:{session}:{region}:{frame_sig}
                        cache_key = f"screen:{session_id}:{region}:{frame_sig}"
                        redis_client.setex(
                            cache_key,
                            SCREEN_CACHE_TTL,
                            json.dumps(analysis_data)
                        )

                        # Secondary key: last_seen:{session}:{region} → frame_sig
                        last_seen_key = f"last_seen:{session_id}:{region}"
                        redis_client.setex(last_seen_key, SCREEN_CACHE_TTL, frame_sig)

                        logger.info(f"💾 Cached analysis: {cache_key[:50]}... (TTL: {SCREEN_CACHE_TTL}s)")
                    except Exception as e:
                        logger.warning(f"Cache write error: {e}")

                latency_ms = (datetime.now() - start_time).total_seconds() * 1000
                analysis_data["latency_ms"] = round(latency_ms, 2)

                log_structured("screen_analysis_complete",
                             session_id=session_id,
                             region=region,
                             frame_sig=frame_sig,
                             source="fresh",
                             latency_ms=round(latency_ms, 2))

                # Record metrics
                screen_analysis_requests.labels(region=region, source="fresh").inc()
                screen_analysis_latency.labels(region=region, source="fresh").observe(latency_ms)

                logger.info("Screen analysis completed successfully")
                return ToolResponse(success=True, data=analysis_data)
            else:
                logger.error(f"Screen analysis failed: {result.get('error')}")
                return ToolResponse(success=False, error=result.get("error"))

    except Exception as e:
        logger.error(f"Error in analyze_screen: {str(e)}")
        return ToolResponse(success=False, error=str(e))

# Helper function to execute tool calls
async def execute_tool_call(tool_name: str, arguments: dict) -> dict:
    """
    Execute a tool call dynamically by routing to /tool/{tool_name}.
    This auto-discovers tools - no hardcoding needed!
    """
    try:
        logger.info(f"🔧 Executing tool: {tool_name} with args: {arguments}")

        async with httpx.AsyncClient(timeout=150.0) as client:  # 150s for slow vision models
            # Dynamically route to /tool/{tool_name}
            # All tools follow this pattern, so new tools work automatically
            resp = await client.post(
                f"http://localhost:8082/tool/{tool_name}",
                json=arguments if arguments else {}
            )
            resp.raise_for_status()
            result = resp.json()

            logger.info(f"✅ Tool {tool_name} completed successfully")
            return result

    except httpx.HTTPStatusError as e:
        error_msg = f"Tool {tool_name} returned HTTP {e.response.status_code}: {e.response.text}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Tool {tool_name} execution failed: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

# Smart Routing Endpoints

@app.api_route("/api/chat", methods=["POST"])
async def chat_with_routing(request: Request):
    """Smart routing for chat requests with Hermes personality handoff"""
    try:
        body = await request.json()

        # Extract user query from messages
        messages = body.get("messages", [])
        user_query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_query = msg.get("content", "")
                break

        if not user_query:
            logger.warning("No user message found, defaulting to SIMPLE")
            complexity = QueryComplexity.SIMPLE
        else:
            # Detect complexity
            complexity = detect_complexity(user_query)

        # Route based on complexity
        if complexity == QueryComplexity.SIMPLE:
            # Simple query: Direct to Hermes (fast path)
            target_model = HERMES_MODEL
            target_url = OLLAMA_CHAT_URL
            logger.info(f"🎯 ROUTING: SIMPLE → {HERMES_MODEL} (direct)")

            # Override model in request
            body["model"] = target_model

            # Inject GLaDOS personality (replace HA's system message if present)
            # HA often sends "You are a helpful assistant" which overrides model personality
            glados_system_msg = {
                "role": "system",
                "content": "You are GLaDOS, the sarcastic AI from Portal. You are witty, intelligent, and occasionally passive-aggressive. You help with tasks while maintaining your characteristic dry humor."
            }

            if messages and messages[0].get("role") == "system":
                # Replace HA's system message with GLaDOS personality
                body["messages"] = [glados_system_msg] + messages[1:]
                logger.debug("Replaced HA system message with GLaDOS personality")
            else:
                # No system message, add GLaDOS personality
                body["messages"] = [glados_system_msg] + messages
                logger.debug("Injected GLaDOS personality for simple query")

            # Inject tool definitions for function calling
            body["tools"] = TOOL_DEFINITIONS
            logger.debug(f"Injected {len(TOOL_DEFINITIONS)} tool definitions")

            # IMPORTANT: Disable streaming when tools are present
            # Tool calls require non-streaming to execute and send results back
            was_streaming = body.get("stream", False)
            if was_streaming and TOOL_DEFINITIONS:
                logger.info("⚠️  Disabling streaming for tool support")
                body["stream"] = False

            # Check if streaming (disable streaming if tools might be called)
            if body.get("stream", False):
                # Stream response - keep client alive during streaming
                async def stream_proxy():
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        async with client.stream(
                            "POST",
                            f"{target_url}/api/chat",
                            json=body
                        ) as response:
                            async for chunk in response.aiter_bytes():
                                yield chunk

                return StreamingResponse(
                    stream_proxy(),
                    media_type="application/x-ndjson"
                )
            else:
                # Regular response with tool call handling
                async with httpx.AsyncClient(timeout=120.0) as client:
                    # Initial request to Ollama
                    response = await client.post(
                        f"{target_url}/api/chat",
                        json=body
                    )
                    response.raise_for_status()
                    response_data = response.json()

                    # Check if response contains tool calls
                    message = response_data.get("message", {})
                    tool_calls = message.get("tool_calls")

                    if tool_calls:
                        tool_names = [tc.get('function', {}).get('name') for tc in tool_calls]
                        logger.info(f"🔧 Tool calls detected: {tool_names}")

                        # IMMEDIATE ACKNOWLEDGEMENT: Stream before executing tools (reduces perceived latency)
                        if was_streaming and tool_names:
                            first_tool = tool_names[0]
                            ack_message = TOOL_ACKNOWLEDGEMENTS.get(first_tool, "One moment...")
                            logger.info(f"🎤 Streaming acknowledgement: '{ack_message}'")

                            # Create a simple acknowledgement response and stream it immediately
                            ack_body = {
                                "model": target_model,
                                "messages": body["messages"] + [{
                                    "role": "user",
                                    "content": f"Say only: '{ack_message}'"
                                }],
                                "stream": True
                            }

                            # Stream acknowledgement BEFORE tool execution
                            async def stream_with_ack_and_tool_execution():
                                # First, stream the acknowledgement
                                async with httpx.AsyncClient(timeout=30.0) as ack_client:
                                    async with ack_client.stream(
                                        "POST",
                                        f"{target_url}/api/chat",
                                        json=ack_body
                                    ) as ack_response:
                                        async for chunk in ack_response.aiter_bytes():
                                            yield chunk

                                # Now execute tools while user hears the acknowledgement
                                logger.info("⚙️  Executing tools in background...")

                                # Add assistant's message with tool calls first
                                body["messages"].append(message)

                                for tool_call in tool_calls:
                                    function = tool_call.get("function", {})
                                    tool_name = function.get("name")
                                    arguments_str = function.get("arguments", "{}")

                                    try:
                                        arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                                    except json.JSONDecodeError:
                                        arguments = {}

                                    tool_result = await execute_tool_call(tool_name, arguments)

                                    # Add tool result to conversation
                                    body["messages"].append({
                                        "role": "tool",
                                        "content": json.dumps(tool_result)
                                    })

                                # Finally, stream the actual response with tool results
                                logger.info("📡 Streaming final response with tool results...")
                                body["stream"] = True
                                async with httpx.AsyncClient(timeout=120.0) as final_client:
                                    async with final_client.stream(
                                        "POST",
                                        f"{target_url}/api/chat",
                                        json=body
                                    ) as final_response:
                                        async for chunk in final_response.aiter_bytes():
                                            yield chunk

                            return StreamingResponse(
                                stream_with_ack_and_tool_execution(),
                                media_type="application/x-ndjson"
                            )

                        # Non-streaming path (no acknowledgement needed)
                        # Add assistant's message with tool calls to conversation
                        body["messages"].append(message)

                        # Execute each tool call
                        for tool_call in tool_calls:
                            function = tool_call.get("function", {})
                            tool_name = function.get("name")
                            arguments_str = function.get("arguments", "{}")

                            # Parse arguments (they come as a JSON string)
                            try:
                                arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                            except json.JSONDecodeError:
                                arguments = {}

                            # Execute the tool
                            tool_result = await execute_tool_call(tool_name, arguments)

                            # Add tool result to messages
                            body["messages"].append({
                                "role": "tool",
                                "content": json.dumps(tool_result)
                            })

                        # Send back to Ollama with tool results for final response
                        # Re-enable streaming if it was originally requested (for TTS)
                        if was_streaming:
                            logger.info("📡 Re-enabling streaming for final response (TTS support)")
                            body["stream"] = True

                            async def stream_final():
                                async with httpx.AsyncClient(timeout=120.0) as stream_client:
                                    async with stream_client.stream(
                                        "POST",
                                        f"{target_url}/api/chat",
                                        json=body
                                    ) as response:
                                        async for chunk in response.aiter_bytes():
                                            yield chunk

                            return StreamingResponse(
                                stream_final(),
                                media_type="application/x-ndjson"
                            )
                        else:
                            logger.info("Sending tool results back to Ollama for final response")
                            final_response = await client.post(
                                f"{target_url}/api/chat",
                                json=body
                            )
                            return Response(
                                content=final_response.content,
                                status_code=final_response.status_code,
                                media_type="application/json"
                            )
                    else:
                        # No tool calls, return response as-is
                        return Response(
                            content=response.content,
                            status_code=response.status_code,
                            media_type="application/json"
                        )

        else:
            # Complex query: Qwen → Hermes handoff for personality consistency
            logger.info(f"🎯 ROUTING: COMPLEX → {QWEN_MODEL} (background) → {HERMES_MODEL} (voice)")

            # Step 1: Send to Qwen for analysis (force non-streaming for handoff)
            qwen_body = body.copy()
            qwen_body["model"] = QWEN_MODEL
            qwen_body["stream"] = False  # Force non-streaming for handoff

            async with httpx.AsyncClient(timeout=120.0) as client:
                logger.debug(f"Querying Qwen for analysis...")
                qwen_response = await client.post(
                    f"{OLLAMA_CHAT_URL}/api/chat",
                    json=qwen_body
                )
                qwen_response.raise_for_status()
                qwen_data = qwen_response.json()

                # Extract Qwen's response
                qwen_content = qwen_data.get("message", {}).get("content", "")
                logger.debug(f"Qwen response: {qwen_content[:100]}...")

                # Step 2: Send Qwen's analysis to Hermes for GLaDOS personality
                hermes_messages = [
                    {
                        "role": "system",
                        "content": "You are GLaDOS. Rephrase the following analysis in your characteristic sarcastic, witty voice. Maintain the factual content but add your personality."
                    },
                    {
                        "role": "user",
                        "content": f"Original question: {user_query}\n\nAnalysis to rephrase: {qwen_content}"
                    }
                ]

                hermes_body = {
                    "model": HERMES_MODEL,
                    "messages": hermes_messages,
                    "stream": body.get("stream", False)  # Match original streaming preference
                }

                logger.debug(f"Sending to Hermes for personality handoff...")

                # Check if streaming
                if hermes_body.get("stream", False):
                    # Stream Hermes response
                    async def stream_hermes():
                        async with httpx.AsyncClient(timeout=120.0) as stream_client:
                            async with stream_client.stream(
                                "POST",
                                f"{OLLAMA_CHAT_URL}/api/chat",
                                json=hermes_body
                            ) as response:
                                async for chunk in response.aiter_bytes():
                                    yield chunk

                    return StreamingResponse(
                        stream_hermes(),
                        media_type="application/x-ndjson"
                    )
                else:
                    # Regular Hermes response
                    hermes_response = await client.post(
                        f"{OLLAMA_CHAT_URL}/api/chat",
                        json=hermes_body
                    )
                    return Response(
                        content=hermes_response.content,
                        status_code=hermes_response.status_code,
                        media_type="application/json"
                    )

    except Exception as e:
        logger.error(f"Error in chat routing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
async def proxy_ollama_api(request: Request, path: str):
    """Pass-through proxy for Ollama API endpoints (except /api/chat which has routing)"""

    # /api/chat is handled separately by chat_with_routing
    if path == "chat":
        raise HTTPException(status_code=500, detail="Should be handled by chat_with_routing")

    target_url = f"{OLLAMA_CHAT_URL}/api/{path}"
    logger.debug(f"Pass-through: {request.method} /api/{path} → {target_url}")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Forward the request
            response = await client.request(
                method=request.method,
                url=target_url,
                content=await request.body(),
                headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            )

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )

    except Exception as e:
        logger.error(f"Proxy error for /api/{path}: {e}")
        raise HTTPException(status_code=502, detail=str(e))

@app.api_route("/healthz", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint"""
    health_status = {
        "service": "glados-orchestrator",
        "version": "2.2.0",
        "status": "healthy",
        "mode": "unified-voice-architecture",
        "letta_bridge": "unknown",
        "ollama_chat": "unknown",
        "kitchen_api": "unknown",
        "overnight_api": "unknown",
        "tools_available": len(TOOL_DEFINITIONS),
        "routing": {
            "simple_model": HERMES_MODEL,
            "complex_model": QWEN_MODEL
        }
    }

    try:
        # Check if Letta Bridge is accessible
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(
                    f"{LETTA_BRIDGE_URL}/healthz",
                    headers={"x-api-key": LETTA_API_KEY}
                )
                resp.raise_for_status()
                health_status["letta_bridge"] = "healthy"
            except httpx.HTTPError as e:
                logger.warning(f"Health check - Letta Bridge error: {str(e)}")
                health_status["letta_bridge"] = "unhealthy"
                health_status["status"] = "degraded"

            # Check Kitchen API
            try:
                resp = await client.get(f"{KITCHEN_API_URL}/healthz")
                resp.raise_for_status()
                health_status["kitchen_api"] = "healthy"
            except httpx.HTTPError as e:
                logger.warning(f"Health check - Kitchen API error: {str(e)}")
                health_status["kitchen_api"] = "unhealthy"
                health_status["status"] = "degraded"

            # Check Overnight API
            try:
                resp = await client.get(f"{OVERNIGHT_API_URL}/healthz")
                resp.raise_for_status()
                health_status["overnight_api"] = "healthy"
            except httpx.HTTPError as e:
                logger.warning(f"Health check - Overnight API error: {str(e)}")
                health_status["overnight_api"] = "unhealthy"
                health_status["status"] = "degraded"

            # Check Ollama connectivity
            try:
                resp = await client.get(f"{OLLAMA_CHAT_URL}/api/tags")
                resp.raise_for_status()
                health_status["ollama_chat"] = "healthy"
            except httpx.HTTPError as e:
                logger.warning(f"Health check - Ollama Chat error: {str(e)}")
                health_status["ollama_chat"] = "unhealthy"
                health_status["status"] = "degraded"

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)

    return health_status

@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "GLaDOS Orchestrator",
        "version": "2.2.0",
        "mode": "unified-voice-architecture",
        "description": "Tool endpoints, intelligent routing, and personality-consistent responses for Ollama LLM",
        "endpoints": {
            "tools": "/tool/list",
            "get_time": "/tool/get_time",
            "letta_query": "/tool/letta_query",
            "execute_ha_skill": "/tool/execute_ha_skill",
            "kitchen_api": "/tool/* (e.g., /tool/add_to_grocery_list)",
            "overnight_api": "/tool/* (e.g., /tool/start_overnight_cycle)",
            "health": "/healthz",
            "chat": "/api/chat (with smart routing)",
            "ollama_api": "/api/* (pass-through to Ollama)"
        },
        "routing": {
            "simple_queries": f"{HERMES_MODEL} (direct, fast path)",
            "complex_queries": f"{QWEN_MODEL} (background analysis) → {HERMES_MODEL} (GLaDOS voice)"
        },
        "usage": "Connect Home Assistant to this orchestrator. Chat queries will be automatically routed. Tools available via function calling."
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting GLaDOS Orchestrator v2.2 - Unified Voice Architecture")
    logger.info(f"Routing: SIMPLE={HERMES_MODEL} (direct), COMPLEX={QWEN_MODEL}→{HERMES_MODEL} (handoff)")
    logger.info(f"Ollama: {OLLAMA_CHAT_URL}")
    logger.info(f"Kitchen API: {KITCHEN_API_URL}")
    logger.info(f"Overnight API: {OVERNIGHT_API_URL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
