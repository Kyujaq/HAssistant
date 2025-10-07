"""
GLaDOS Orchestrator - Tool Provider for Ollama LLM

Provides specialized tools for Ollama-based conversation agents:
- Memory integration via Letta Bridge
- Time and date utilities
- Home Assistant skill execution
- Custom GLaDOS personality tools

Architecture:
- Home Assistant connects directly to Ollama
- Ollama models use this service as a tool provider
- Tools are exposed via REST API endpoints

Features:
- RESTful tool endpoints for LLM function calling
- Integrates with Letta Bridge for persistent memory
- Lightweight, stateless service design
- Debug logging for troubleshooting
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Header
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

app = FastAPI(
    title="GLaDOS Orchestrator - Tool Provider",
    version="2.0.0",
    description="Tool endpoints for Ollama LLM function calling"
)

# Pydantic models for tool requests/responses
class ToolResponse(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None

class LettaQueryRequest(BaseModel):
    query: str
    limit: int = 5

class HASkillRequest(BaseModel):
    skill_name: str
    parameters: Dict[str, Any] = {}

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
    }
]

# Helper functions for memory integration

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
        "version": "2.0.0",
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

@app.api_route("/healthz", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint"""
    health_status = {
        "service": "glados-orchestrator",
        "version": "2.0.0",
        "status": "healthy",
        "mode": "tool-provider",
        "letta_bridge": "unknown",
        "tools_available": len(TOOL_DEFINITIONS)
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
        "version": "2.0.0",
        "mode": "tool-provider",
        "description": "Provides specialized tools for Ollama LLM function calling",
        "endpoints": {
            "tools": "/tool/list",
            "get_time": "/tool/get_time",
            "letta_query": "/tool/letta_query",
            "execute_ha_skill": "/tool/execute_ha_skill",
            "health": "/healthz"
        },
        "usage": "Connect Home Assistant directly to Ollama, then configure Ollama to use these tool endpoints"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
