"""
GLaDOS Orchestrator - Intelligent routing between Qwen (brain) and Hermes (personality)

Routes queries to:
- Simple queries → Hermes directly (fast, personality only)
- Complex queries → Qwen for reasoning → Hermes for personality (accurate + GLaDOS voice)
"""

import os
import re
from typing import Dict, List, Optional, Any
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama-chat:11434")
QWEN_MODEL = os.getenv("QWEN_MODEL", "glados-qwen")
HERMES_MODEL = os.getenv("HERMES_MODEL", "glados-hermes3")
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
    created: int = 0
    model: str = "glados"
    choices: List[Dict[str, Any]]

class QueryComplexity(Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"

# Simple query patterns (use Hermes only)
SIMPLE_PATTERNS = [
    r'\b(turn|set|dim|brighten|switch)\s+(on|off)\b',  # Device control
    r'\b(what|tell|give)\s+(time|temperature|weather)\b',  # Simple facts
    r'\b(open|close|lock|unlock)\b',  # Direct commands
    r'\b(play|pause|stop|skip|next|previous)\b',  # Media control
]

# Complex query patterns (use Qwen brain + Hermes personality)
COMPLEX_PATTERNS = [
    r'\b(plan|schedule|organize|arrange)\b',  # Planning
    r'\b(if|when|then|based\s+on|considering)\b',  # Conditional logic
    r'\b(why|how\s+many|compare|analyze)\b',  # Analysis
    r'\b(remember|recall|what\s+did|have\s+I)\b',  # Memory queries
    r'\b(calendar|appointment|meeting|event)\b',  # Calendar integration
]

def detect_complexity(query: str) -> QueryComplexity:
    """Determine if query is simple or complex"""
    query_lower = query.lower()

    # Check word count (very short = simple)
    word_count = len(query_lower.split())
    if word_count <= 5:
        return QueryComplexity.SIMPLE

    # Check for complex patterns first (higher priority)
    for pattern in COMPLEX_PATTERNS:
        if re.search(pattern, query_lower):
            return QueryComplexity.COMPLEX

    # Check for simple patterns
    for pattern in SIMPLE_PATTERNS:
        if re.search(pattern, query_lower):
            return QueryComplexity.SIMPLE

    # Default: if > 15 words, treat as complex; otherwise simple
    return QueryComplexity.COMPLEX if word_count > 15 else QueryComplexity.SIMPLE

async def call_ollama(model: str, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
    """Call Ollama API and return response"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }

        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        return result.get("message", {}).get("content", "")

async def process_simple_query(messages: List[Message], temperature: float) -> str:
    """Process simple query with Hermes only (fast path)"""
    msgs = [{"role": m.role, "content": m.content} for m in messages]
    response = await call_ollama(HERMES_MODEL, msgs, temperature)
    return response

async def process_complex_query(messages: List[Message], temperature: float) -> str:
    """Process complex query: Qwen brain → Hermes personality"""

    # Step 1: Get Qwen's reasoning (with thinking enabled)
    user_query = messages[-1].content if messages else ""

    # Build context from message history
    context_msgs = [{"role": m.role, "content": m.content} for m in messages[:-1]]

    # Add instruction for Qwen to think through the problem
    qwen_msgs = context_msgs + [{
        "role": "user",
        "content": f"{user_query}\n\nThink through this step by step and provide your analysis."
    }]

    qwen_response = await call_ollama(QWEN_MODEL, qwen_msgs, temperature)

    # Step 2: Extract the factual answer from Qwen's response
    # Remove <think> tags if present
    factual_answer = re.sub(r'<think>.*?</think>', '', qwen_response, flags=re.DOTALL).strip()
    if not factual_answer:
        factual_answer = qwen_response  # Fallback to full response

    # Step 3: Pass to Hermes for GLaDOS personality
    hermes_msgs = [{
        "role": "system",
        "content": "You are GLaDOS. The following is factual information. Respond with your characteristic sarcastic wit and personality."
    }, {
        "role": "user",
        "content": f"Based on this information: {factual_answer}\n\nRespond to the original query: {user_query}"
    }]

    hermes_response = await call_ollama(HERMES_MODEL, hermes_msgs, temperature * 0.9)
    return hermes_response

@app.post("/v1/chat/completions")
async def chat_completion(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """OpenAI-compatible chat completion endpoint"""

    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    # Get the user's query
    user_query = request.messages[-1].content

    # Detect complexity
    complexity = detect_complexity(user_query)

    # Route to appropriate handler
    if complexity == QueryComplexity.SIMPLE:
        response_text = await process_simple_query(request.messages, request.temperature or 0.7)
    else:
        response_text = await process_complex_query(request.messages, request.temperature or 0.7)

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

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "glados-orchestrator"}

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
