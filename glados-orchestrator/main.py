"""
GLaDOS Orchestrator - Intelligent routing between Qwen (brain) and Hermes (personality)

Routes queries to:
- Simple queries → Hermes directly (fast, personality only)
- Complex queries → Qwen for reasoning → Hermes for personality (accurate + GLaDOS voice)

Features:
- Respects custom system prompts from Home Assistant
- Integrates with Letta Bridge for persistent memory
- Streaming support for real-time responses
- Debug logging for troubleshooting
"""

import os
import re
import time
import json
import logging
from typing import Dict, List, Optional, Any, AsyncIterator
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("glados-orchestrator")

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama-chat:11434")
QWEN_MODEL = os.getenv("QWEN_MODEL", "glados-qwen")
HERMES_MODEL = os.getenv("HERMES_MODEL", "glados-hermes3")
LETTA_BRIDGE_URL = os.getenv("LETTA_BRIDGE_URL", "http://hassistant-letta-bridge:8081")
LETTA_API_KEY = os.getenv("LETTA_API_KEY", "d6DkfuU7zPOpcoeAVabiNNPhTH6TcFrZ")
PORT = int(os.getenv("PORT", "8082"))

app = FastAPI(title="GLaDOS Orchestrator", version="1.0.0")

# OpenAI-compatible request/response models
class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "glados"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False

class ChatCompletionResponse(BaseModel):
    id: str = "chatcmpl-glados"
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "glados"
    choices: List[Dict[str, Any]]

class QueryComplexity(Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"

# Compiled regex patterns for performance (compiled once at module load)
# Simple query patterns (use Hermes only) - VERY BROAD to catch most queries
SIMPLE_PATTERNS = [
    re.compile(r'\b(turn|set|dim|brighten|switch)\s+(on|off)\b', re.IGNORECASE),
    re.compile(r'\b(what|tell|give|show)\b', re.IGNORECASE),
    re.compile(r'\b(open|close|lock|unlock)\b', re.IGNORECASE),
    re.compile(r'\b(play|pause|stop|skip|next|previous)\b', re.IGNORECASE),
    re.compile(r'\b(hello|hi|hey|good morning|good evening)\b', re.IGNORECASE),
    re.compile(r'\b(how are you|how\'s it going|what\'s up)\b', re.IGNORECASE),
    re.compile(r'\b(thank|thanks|please)\b', re.IGNORECASE),
]

# Complex query patterns (use Qwen brain ONLY for truly complex reasoning)
COMPLEX_PATTERNS = [
    re.compile(r'\b(plan|schedule|organize|arrange)\s+(my|a|the)\b', re.IGNORECASE),
    re.compile(r'\b(calendar|appointment|meeting)\s+(on|at|for|tomorrow|next)\b', re.IGNORECASE),
    re.compile(r'\b(if.*then|when.*then)\b', re.IGNORECASE),
    re.compile(r'\b(compare|analyze)\s+\w+\s+(with|and|versus)\b', re.IGNORECASE),
]

def detect_complexity(query: str) -> QueryComplexity:
    """Determine if query is simple or complex - BIASED TOWARD SIMPLE for speed"""
    query_lower = query.lower()
    word_count = len(query_lower.split())

    logger.debug(f"Complexity detection: '{query_lower}' (words: {word_count})")

    # Check for complex patterns first (they take priority)
    for pattern in COMPLEX_PATTERNS:
        if pattern.search(query_lower):
            logger.info(f"Matched complex pattern: {pattern.pattern}")
            return QueryComplexity.COMPLEX

    # Check for simple patterns
    for pattern in SIMPLE_PATTERNS:
        if pattern.search(query_lower):
            logger.info(f"Matched simple pattern: {pattern.pattern}")
            return QueryComplexity.SIMPLE

    # Word count heuristic
    if word_count <= 10:
        logger.info("Classified as SIMPLE (≤10 words)")
        return QueryComplexity.SIMPLE
    elif word_count > 15:
        logger.info("Classified as COMPLEX (>15 words)")
        return QueryComplexity.COMPLEX

    # Default: SIMPLE for 11-15 word queries (prioritize speed)
    logger.info("Classified as SIMPLE (default)")
    return QueryComplexity.SIMPLE

def messages_to_dict(messages: List[Message]) -> List[Dict[str, str]]:
    """Convert Message objects to dict format for Ollama API"""
    return [{"role": m.role, "content": m.content} for m in messages]

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

async def call_ollama(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    stream: bool = False
) -> str:
    """Call Ollama API and return response (non-streaming)"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                }
            }

            if max_tokens:
                payload["options"]["num_predict"] = max_tokens

            logger.debug(f"Calling Ollama: model={model}, msgs={len(messages)}, temp={temperature}")

            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result.get("message", {}).get("content", "")

    except httpx.HTTPError as e:
        logger.error(f"Ollama API error for model '{model}': {str(e)}")
        raise HTTPException(status_code=502, detail=f"Ollama API error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error calling Ollama: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

async def call_ollama_stream(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> AsyncIterator[str]:
    """Call Ollama API and stream response chunks"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                }
            }

            if max_tokens:
                payload["options"]["num_predict"] = max_tokens

            logger.debug(f"Streaming Ollama: model={model}, msgs={len(messages)}")

            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=60.0
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            if content := chunk.get("message", {}).get("content"):
                                yield content
                        except json.JSONDecodeError:
                            continue

    except httpx.HTTPError as e:
        logger.error(f"Ollama streaming error for model '{model}': {str(e)}")
        raise HTTPException(status_code=502, detail=f"Ollama API error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected streaming error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

async def process_simple_query(messages: List[Message], temperature: float, user_query: str) -> str:
    """Process simple query with Hermes only (fast path - NO MEMORY for speed)"""
    try:
        # Skip memory retrieval for simple queries to maximize speed
        msgs = messages_to_dict(messages)

        logger.info(f"Processing SIMPLE query (fast path - no memory)")
        # Limit to 100 tokens (~2-3 sentences) for speed
        response = await call_ollama(HERMES_MODEL, msgs, temperature, max_tokens=100)

        # Skip saving to memory for simple queries (reduces overhead)
        # Only complex/important queries need memory persistence

        return response

    except Exception as e:
        logger.error(f"Error in simple query processing: {str(e)}")
        raise

async def process_complex_query(messages: List[Message], temperature: float, user_query: str) -> str:
    """Process complex query: Qwen brain → Hermes personality (preserves conversation context)"""
    try:
        # Retrieve only 2 most relevant memories (reduced from 5 for speed)
        memories = await retrieve_memory(user_query, limit=2)

        # Extract custom system prompt if present and preserve conversation history
        custom_system_prompt = None
        conversation_history = []
        for m in messages:
            if m.role == "system":
                custom_system_prompt = m.content
            else:
                conversation_history.append({"role": m.role, "content": m.content})

        # Build memory context
        memory_context = ""
        if memories:
            memory_context = "Relevant context from past interactions:\n"
            for mem in memories:
                memory_context += f"- {mem.get('title', '')}: {mem.get('content', '')}\n"
            memory_context += "\n"

        # Step 1: Get Qwen's reasoning with memory context
        # Augment the last user message with memory context
        qwen_msgs = conversation_history[:-1] + [{
            "role": "user",
            "content": f"{memory_context}{user_query}\n\nThink through this step by step and provide your analysis."
        }]

        logger.info(f"Processing COMPLEX query with {len(memories)} memories")
        # Use lower temperature (0.5) for faster, more focused generation
        # Limit Qwen to 200 tokens for concise reasoning
        qwen_response = await call_ollama(QWEN_MODEL, qwen_msgs, 0.5, max_tokens=200)

        # Step 2: Extract the factual answer from Qwen's response
        factual_answer = re.sub(r'<think>.*?</think>', '', qwen_response, flags=re.DOTALL).strip()
        if not factual_answer:
            factual_answer = qwen_response

        # Step 3: Pass FULL conversation + Qwen's reasoning to Hermes for personality
        # This preserves multi-turn context while adding Qwen's analysis
        if custom_system_prompt:
            system_content = f"{custom_system_prompt}\n\nYou have access to this factual analysis: {factual_answer}"
        else:
            system_content = f"You are GLaDOS. Use this factual analysis to inform your response: {factual_answer}"

        # Preserve full conversation history when passing to Hermes
        hermes_msgs = [{"role": "system", "content": system_content}] + conversation_history

        # Limit Hermes to 100 tokens for concise GLaDOS responses
        hermes_response = await call_ollama(HERMES_MODEL, hermes_msgs, temperature * 0.9, max_tokens=100)

        # Save this interaction to memory (tier=medium for complex queries)
        await save_memory(
            title=f"Complex query: {user_query[:50]}",
            content=f"Q: {user_query}\nReasoning: {factual_answer[:200]}\nA: {hermes_response}",
            tier="medium"
        )

        return hermes_response

    except Exception as e:
        logger.error(f"Error in complex query processing: {str(e)}")
        raise

@app.post("/v1/api/chat")
@app.post("/api/chat")
async def ollama_chat(request: Dict[str, Any]):
    """Ollama-compatible /api/chat endpoint"""
    # Convert Ollama format to OpenAI format
    messages = [Message(**msg) for msg in request.get("messages", [])]
    openai_request = ChatCompletionRequest(
        model=request.get("model", "glados"),
        messages=messages,
        temperature=request.get("options", {}).get("temperature", 0.7),
        stream=request.get("stream", False)
    )

    # Process through OpenAI endpoint
    response = await chat_completion(openai_request)

    # Convert back to Ollama format
    return {
        "model": request.get("model", "glados"),
        "created_at": "2025-10-04T00:00:00Z",
        "message": response.choices[0]["message"],
        "done": True
    }

async def generate_stream(
    messages: List[Message],
    temperature: float,
    user_query: str,
    complexity: QueryComplexity
):
    """Generate streaming response in OpenAI format"""
    try:
        # For streaming, we route to the appropriate model(s)
        if complexity == QueryComplexity.SIMPLE:
            # Stream directly from Hermes
            msgs = messages_to_dict(messages)
            async for chunk in call_ollama_stream(HERMES_MODEL, msgs, temperature):
                yield f"data: {json.dumps({'choices': [{'delta': {'content': chunk}, 'index': 0}]})}\n\n"
        else:
            # For complex: Get Qwen response (non-streaming), then stream Hermes
            # We can't stream Qwen's internal reasoning, so we get it first
            qwen_response = await process_complex_query(messages, temperature, user_query)
            # Then stream the final response (note: already processed, so we just send it)
            yield f"data: {json.dumps({'choices': [{'delta': {'content': qwen_response}, 'index': 0}]})}\n\n"

        # Send done message
        yield f"data: {json.dumps({'choices': [{'finish_reason': 'stop', 'index': 0}]})}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        error_msg = f"data: {json.dumps({'error': str(e)})}\n\n"
        yield error_msg

@app.post("/v1/chat/completions")
async def chat_completion(request: ChatCompletionRequest):
    """OpenAI-compatible chat completion endpoint (supports streaming)"""

    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    # Get the user's query
    user_query = request.messages[-1].content

    # Log incoming request
    logger.info(f"Incoming request - Messages: {len(request.messages)}, Query: {user_query[:100]}...")
    for i, msg in enumerate(request.messages):
        logger.debug(f"  Message {i}: {msg.role} - {msg.content[:100]}...")

    # Detect complexity
    complexity = detect_complexity(user_query)
    logger.info(f"Detected complexity: {complexity.value}")

    # Handle streaming vs non-streaming
    if request.stream:
        logger.info("Streaming response requested")
        return StreamingResponse(
            generate_stream(request.messages, request.temperature or 0.7, user_query, complexity),
            media_type="text/event-stream"
        )

    # Non-streaming response
    try:
        # Route to appropriate handler
        if complexity == QueryComplexity.SIMPLE:
            response_text = await process_simple_query(request.messages, request.temperature or 0.7, user_query)
        else:
            response_text = await process_complex_query(request.messages, request.temperature or 0.7, user_query)

        logger.info(f"Response generated: {response_text[:100]}...")

        # Return OpenAI-compatible response
        return ChatCompletionResponse(
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/v1/api/tags")
@app.get("/api/tags")
async def list_models():
    """Ollama-compatible endpoint for Home Assistant integration"""
    return {
        "models": [
            {
                "name": "glados",
                "model": "glados",
                "modified_at": "2025-10-04T00:00:00Z",
                "size": 0,
                "digest": "glados-orchestrator",
                "details": {
                    "parent_model": "",
                    "format": "gguf",
                    "family": "llama",
                    "families": ["llama"],
                    "parameter_size": "7B",
                    "quantization_level": "Q4_K_M"
                }
            }
        ]
    }

@app.get("/healthz")
async def health_check():
    """Health check endpoint (checks Ollama and models availability)"""
    health_status = {
        "service": "glados-orchestrator",
        "status": "healthy",
        "ollama": "unknown",
        "models": {}
    }

    try:
        # Check if Ollama is running
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                resp.raise_for_status()
                health_status["ollama"] = "healthy"

                # Check if our specific models are loaded
                models_list = resp.json().get("models", [])
                model_names = {m.get("name", "") for m in models_list}

                # Check Qwen model
                qwen_available = any(QWEN_MODEL in name for name in model_names)
                health_status["models"]["qwen"] = "available" if qwen_available else "missing"

                # Check Hermes model
                hermes_available = any(HERMES_MODEL in name for name in model_names)
                health_status["models"]["hermes"] = "available" if hermes_available else "missing"

                # Overall status
                if not qwen_available or not hermes_available:
                    health_status["status"] = "degraded"

            except httpx.HTTPError as e:
                logger.error(f"Health check - Ollama error: {str(e)}")
                health_status["ollama"] = "unhealthy"
                health_status["status"] = "unhealthy"

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
        "version": "1.0.0",
        "models": {
            "brain": QWEN_MODEL,
            "personality": HERMES_MODEL
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
