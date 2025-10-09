#!/usr/bin/env python3
"""
POC Smart Routing Proxy for Ollama

Tests transparent pass-through for model management + smart routing for chat.

Architecture:
- HA → Smart Proxy (port 8090) → Ollama containers
- Pass-through: /api/tags, /api/pull, /api/show, etc. → ollama-chat:11434
- Smart routing: /api/chat → complexity detection → route to appropriate model
"""

import re
import logging
from typing import Dict, List, Optional, Any
from enum import Enum

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("poc-smart-proxy")

# Configuration
OLLAMA_CHAT_URL = "http://ollama-chat:11434"  # Container network
OLLAMA_VISION_URL = "http://ollama-vision:11434"  # Container network (internal port)
PORT = 8090

# Model configuration
HERMES_MODEL = "glados-hermes3"
QWEN_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
VISION_MODEL = "qwen2.5vl:7b"

app = FastAPI(title="POC Smart Proxy", version="0.1.0")

class QueryComplexity(Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"

# Simple query patterns (use Hermes only)
SIMPLE_PATTERNS = [
    re.compile(r'\b(turn|set|dim|brighten|switch)\s+(on|off)\b', re.IGNORECASE),
    re.compile(r'\b(what|tell|give|show)\b', re.IGNORECASE),
    re.compile(r'\b(open|close|lock|unlock)\b', re.IGNORECASE),
    re.compile(r'\b(play|pause|stop|skip|next|previous)\b', re.IGNORECASE),
    re.compile(r'\b(hello|hi|hey|good morning|good evening)\b', re.IGNORECASE),
    re.compile(r'\b(how are you|how\'s it going|what\'s up)\b', re.IGNORECASE),
    re.compile(r'\b(thank|thanks|please)\b', re.IGNORECASE),
]

# Complex query patterns (use Qwen)
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

@app.get("/")
async def root():
    """Service info"""
    return {
        "service": "POC Smart Routing Proxy",
        "version": "0.1.0",
        "status": "running",
        "routes": {
            "pass_through": ["/api/tags", "/api/pull", "/api/show", "/api/delete", "/api/push"],
            "smart_routing": ["/api/chat"],
            "target": OLLAMA_CHAT_URL
        }
    }

@app.get("/healthz")
async def health():
    """Health check"""
    return {"status": "healthy", "proxy": "running"}

@app.api_route("/api/chat", methods=["POST"])
async def chat(request: Request):
    """Smart routing for chat requests"""
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
            target_model = HERMES_MODEL
            target_url = OLLAMA_CHAT_URL
            logger.info(f"🎯 ROUTING: SIMPLE → {HERMES_MODEL}")
        else:
            target_model = QWEN_MODEL
            target_url = OLLAMA_CHAT_URL
            logger.info(f"🎯 ROUTING: COMPLEX → {QWEN_MODEL}")

        # Override model in request
        body["model"] = target_model

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

    except Exception as e:
        logger.error(f"Error in chat routing: {e}")
        return {"error": str(e)}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
async def proxy_all(request: Request, path: str):
    """Pass-through proxy for all other Ollama endpoints"""
    target_url = f"{OLLAMA_CHAT_URL}/{path}"

    logger.debug(f"Pass-through: {request.method} /{path} → {target_url}")

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
        logger.error(f"Proxy error for /{path}: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting POC Smart Proxy on port {PORT}")
    logger.info(f"Target: {OLLAMA_CHAT_URL}")
    logger.info(f"Models: SIMPLE={HERMES_MODEL}, COMPLEX={QWEN_MODEL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
