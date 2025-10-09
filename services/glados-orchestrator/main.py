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
"""

import re
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("glados-orchestrator")

# Configuration
LETTA_BRIDGE_URL = os.getenv("LETTA_BRIDGE_URL", "http://hassistant-letta-bridge:8081")
LETTA_API_KEY = os.getenv("LETTA_API_KEY", "d6DkfuU7zPOpcoeAVabiNNPhTH6TcFrZ")
PORT = int(os.getenv("PORT", "8082"))

# Kitchen and Overnight API configuration
KITCHEN_API_URL = os.getenv("KITCHEN_API_URL", "http://hassistant-kitchen-api:8083")
OVERNIGHT_API_URL = os.getenv("OVERNIGHT_API_URL", "http://hassistant-overnight:8084")

# Ollama configuration for routing
OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://ollama-chat:11434")
OLLAMA_VISION_URL = os.getenv("OLLAMA_VISION_URL", "http://ollama-vision:11434")
HERMES_MODEL = os.getenv("HERMES_MODEL", "glados-hermes3")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen2.5vl:7b")

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
    quantity: int
    expiry_date: Optional[str] = None

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
                    "quantity": {"type": "integer", "description": "The quantity of the item."},
                    "notes": {"type": "string", "description": "Any notes for the item."}
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
            "description": "Add an item to the inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The name of the item."},
                    "quantity": {"type": "integer", "description": "The quantity of the item."},
                    "expiry_date": {"type": "string", "description": "The expiry date in YYYY-MM-DD format."}
                },
                "required": ["name", "quantity"]
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
    }
]

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
                json=request.dict()
            )
            response.raise_for_status()
            return ToolResponse(success=True, data=response.json())
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
    """Add an item to the inventory via kitchen-api."""
    try:
        logger.info(f"add_inventory_item called with item: {request.name}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{KITCHEN_API_URL}/inventory/items",
                json=request.dict()
            )
            response.raise_for_status()
            return ToolResponse(success=True, data=response.json())
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
            response = await client.post(f"{OVERNIGHT_API_URL}/cycle/start")
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
            response = await client.get(f"{OVERNIGHT_API_URL}/cycle/status")
            response.raise_for_status()
            return ToolResponse(success=True, data=response.json())
    except Exception as e:
        logger.error(f"Error in get_overnight_cycle_status: {str(e)}")
        return ToolResponse(success=False, error=str(e))

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

            # Check if streaming
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
                # Regular response
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        f"{target_url}/api/chat",
                        json=body
                    )
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

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting GLaDOS Orchestrator v2.2 - Unified Voice Architecture")
    logger.info(f"Routing: SIMPLE={HERMES_MODEL} (direct), COMPLEX={QWEN_MODEL}→{HERMES_MODEL} (handoff)")
    logger.info(f"Ollama: {OLLAMA_CHAT_URL}")
    logger.info(f"Kitchen API: {KITCHEN_API_URL}")
    logger.info(f"Overnight API: {OVERNIGHT_API_URL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
