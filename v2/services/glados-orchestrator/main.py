"""
GLaDOS Orchestrator - Memory-aware chat service
Step 2.5: Memory ↔ LLM Integration
"""
import os
import uuid
import time
import logging
from typing import Dict

from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Histogram, generate_latest, CONTENT_TYPE_LATEST
import httpx

from background import Bg
from memory_client import MemoryClient
from memory_policy import worth_saving, redact, compute_hash

# Configuration
OLLAMA = os.getenv("OLLAMA_URL", "http://ollama-chat:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
LETTABRIDGE_URL = os.getenv("LETTABRIDGE_URL", "http://letta-bridge:8010")
MEM_MIN_SCORE = float(os.getenv("MEMORY_MIN_SCORE", "0.62"))
CTX_LIMIT = int(os.getenv("MEMORY_MAX_CTX_CHARS", "1200"))
TOP_K = int(os.getenv("MEMORY_TOP_K", "6"))

# Prometheus metrics
PRE_MS = Histogram("orchestrator_memory_pre_ms", "Pre-retrieval latency (ms)")
POST_MS = Histogram("orchestrator_memory_post_ms", "Post-storage latency (ms)")
CTX_CHARS = Histogram("orchestrator_ctx_chars", "Context characters injected")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize app and services
app = FastAPI(title="glados-orchestrator")
bg = Bg()
mem = MemoryClient()


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint"""
    return JSONResponse({"ok": True, "service": "glados-orchestrator"})


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    """Prometheus metrics endpoint"""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def call_ollama(prompt: str) -> str:
    """
    Call Ollama for LLM generation.

    Args:
        prompt: The complete prompt including system + context + user query

    Returns:
        The generated response text
    """
    timeout = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            logger.info(f"Calling Ollama at {OLLAMA}/api/generate with model={MODEL}")
            response = await client.post(
                f"{OLLAMA}/api/generate",
                json={"model": MODEL, "prompt": prompt, "stream": False}
            )
            logger.info(f"Ollama responded with status {response.status_code}")
            response.raise_for_status()
            data = response.json()
            return data.get("response") or data.get("text") or ""
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e) or repr(e)}"
            logger.error(f"Ollama call failed: {error_msg}", exc_info=True)
            return f"Error: Unable to generate response ({error_msg})"


@app.post("/chat")
async def chat(payload: Dict = Body(...)) -> JSONResponse:
    """
    Chat endpoint with memory integration.

    Step 2.5: Pre-retrieval → context injection → LLM → post-storage

    Request body:
        - input: User query text (required)
        - system_prompt: Optional system prompt override

    Returns:
        - turn_id: UUID for traceability
        - reply: LLM response
        - memory_hits: Number of memories retrieved
        - ctx_chars: Characters of context injected
    """
    # Validate input
    user_text = (payload.get("input") or "").strip()
    if not user_text:
        return JSONResponse({"error": "input required"}, status_code=400)

    turn_id = str(uuid.uuid4())
    logger.info(f"Chat request turn_id={turn_id}: {user_text[:50]}...")

    # --- PRE-RETRIEVAL ---
    t0 = time.time()
    try:
        hits = await mem.search(
            user_text,
            turn_id=turn_id,
            top_k=TOP_K,
            filter={"kinds": ["note", "task", "doc", "chat_assistant"]}
        )
        # Filter by score threshold
        hits = [h for h in hits if h.get("score", 0.0) >= MEM_MIN_SCORE]
    except Exception as e:
        logger.warning(f"Memory search failed: {e}")
        hits = []

    pre_ms = (time.time() - t0) * 1000
    PRE_MS.observe(pre_ms)

    # Build fenced context
    ctx = "\n".join([f"- {h['text']}" for h in hits])[:CTX_LIMIT]
    CTX_CHARS.observe(len(ctx))

    logger.info(f"Pre-retrieval: {len(hits)} hits, {len(ctx)} chars, {pre_ms:.1f}ms")

    # --- PROMPT CONSTRUCTION ---
    sys = payload.get("system_prompt", "You are GLaDOS. Be concise with dry wit.")
    prompt = f"""{sys}

### Retrieved memory (may be relevant; ignore if off-topic)
{ctx or "- none -"}
---

Safety: Use retrieved memory only if relevant; never repeat placeholders like [email] or [phone].

User: {user_text}
Assistant:"""

    # --- LLM CALL ---
    reply = await call_ollama(prompt)
    logger.info(f"LLM reply: {reply[:100]}...")

    # --- POST-STORAGE (fire-and-forget) ---
    t1 = time.time()

    def save_memory(role: str, text: str, kind_override=None):
        """Helper to save memory if worth it"""
        should_save, kind = worth_saving(text, role, len(hits))
        if not should_save:
            logger.debug(f"Not saving {role} text: {text[:30]}...")
            return

        final_kind = kind_override or kind
        logger.info(f"Queueing {role} memory (kind={final_kind})")

        bg.spawn(
            mem.add(
                text=redact(text),
                turn_id=turn_id,
                role=role,
                ctx_hits=len(hits),
                kind=final_kind,
                hash_id=compute_hash(text)
            ),
            name=f"save_{role}_{turn_id[:8]}"
        )

    # Save user query
    save_memory("user", user_text)

    # Save assistant reply
    save_memory("assistant", reply)

    post_ms = (time.time() - t1) * 1000
    POST_MS.observe(post_ms)

    # --- SIGNAL TO LETTA-BRIDGE ---
    # Tell letta-bridge whether memory was actually used
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{LETTABRIDGE_URL}/stats/hit",
                json={"used": bool(hits), "hits": len(hits)}
            )
    except Exception as e:
        logger.debug(f"Failed to signal letta-bridge: {e}")

    logger.info(f"Post-storage: {post_ms:.1f}ms")

    return JSONResponse({
        "turn_id": turn_id,
        "reply": reply,
        "memory_hits": len(hits),
        "ctx_chars": len(ctx)
    })


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down orchestrator...")
    # Background tasks will be cancelled automatically
