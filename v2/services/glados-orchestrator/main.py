"""
GLaDOS Orchestrator - Memory-aware chat service with intelligent routing
Step 2.5: Memory ↔ LLM Integration
Step 2.6: VL Router - GPU-aware model selection
"""
import os
import uuid
import time
import logging
from typing import Dict
from collections import defaultdict, deque

from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Histogram, Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
import httpx

from background import Bg
from memory_client import MemoryClient
from memory_policy import worth_saving, redact, compute_hash
from nvml import sample_vl, get_gpu_info

# Ollama endpoints configuration
OLLAMA_TEXT_URL = os.getenv("OLLAMA_TEXT_URL", "http://ollama-text:11434")
OLLAMA_VL_URL = os.getenv("OLLAMA_VL_URL", "http://ollama-vl:11434")

# Model configuration
TEXT_MODEL_FAST = os.getenv("OLLAMA_TEXT_MODEL_FAST", "hermes3:latest")
TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "qwen3:4b")
VL_MODEL = os.getenv("OLLAMA_MODEL_VL", "qwen2.5:3b")

# Memory configuration
LETTABRIDGE_URL = os.getenv("LETTABRIDGE_URL", "http://letta-bridge:8010")
MEM_MIN_SCORE = float(os.getenv("MEMORY_MIN_SCORE", "0.62"))
CTX_LIMIT = int(os.getenv("MEMORY_MAX_CTX_CHARS", "1200"))
TOP_K = int(os.getenv("MEMORY_TOP_K", "6"))

# Router configuration
VL_IDLE_UTIL_MAX = float(os.getenv("VL_IDLE_UTIL_MAX", "0.50"))
VL_MIN_MEM_FREE_GB = float(os.getenv("VL_MIN_MEM_FREE_GB", "3.0"))
VL_QUEUE_MAX_WAIT_MS = int(os.getenv("VL_QUEUE_MAX_WAIT_MS", "400"))
VL_TEXT_ENABLED = os.getenv("VL_TEXT_ENABLED", "1") == "1"
VL_STICKY_TURNS_MIN = int(os.getenv("VL_STICKY_TURNS_MIN", "5"))
VL_TEXT_TOKEN_LIMIT = int(os.getenv("VL_TEXT_TOKEN_LIMIT", "768"))

# Prometheus metrics - Memory
PRE_MS = Histogram("orchestrator_memory_pre_ms", "Pre-retrieval latency (ms)")
POST_MS = Histogram("orchestrator_memory_post_ms", "Post-storage latency (ms)")
CTX_CHARS = Histogram("orchestrator_ctx_chars", "Context characters injected")

# Prometheus metrics - Router
ROUTE_VL_HITS = Counter("route_vl_text_hits", "Text queries routed to VL")
ROUTE_VL_FALLBACKS = Counter("route_vl_text_fallbacks", "VL text fallbacks to 4B")
ROUTE_FAST_HITS = Counter("route_fast_hits", "Fast/simple queries to Hermes")
ROUTE_4B_HITS = Counter("route_4b_hits", "Deeper queries to Qwen3-4B")
VL_QUEUE_G = Gauge("orchestrator_vl_queue_len", "VL queue length")
VL_IDLE_G = Gauge("orchestrator_vl_idle", "1 if VL idle else 0")
VL_UTIL_G = Gauge("orchestrator_vl_util", "VL GPU utilization (5s avg)")
VL_MEM_FREE_G = Gauge("orchestrator_vl_mem_free_gb", "VL GPU free VRAM (GB)")

# Router state
vl_queue = deque(maxlen=64)  # Lightweight queue tracker
conv_sticky_until = defaultdict(float)  # conv_id -> unix timestamp for VL stickiness

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


@app.get("/gpu")
async def gpu_info() -> JSONResponse:
    """Get VL GPU information for debugging"""
    return JSONResponse(get_gpu_info())


@app.get("/router/vl_text_enabled")
async def vl_toggle_state() -> JSONResponse:
    """Get current VL text routing state (HA integration)"""
    return JSONResponse({"enabled": VL_TEXT_ENABLED})


@app.post("/router/vl_text_enabled")
async def vl_toggle(payload: dict = Body(...)) -> JSONResponse:
    """Toggle VL text routing on/off (HA integration)"""
    global VL_TEXT_ENABLED
    VL_TEXT_ENABLED = bool(payload.get("enabled", True))
    logger.info(f"VL text routing: {'enabled' if VL_TEXT_ENABLED else 'disabled'}")
    return JSONResponse({"enabled": VL_TEXT_ENABLED})


# ===== Routing Helpers =====

def vl_idle() -> bool:
    """
    Check if VL GPU is idle and available for text routing.

    Returns:
        True if VL is idle (low util, sufficient VRAM, no queue), False otherwise
    """
    util, mem_free = sample_vl()
    VL_UTIL_G.set(util)
    VL_MEM_FREE_G.set(mem_free)

    idle = (util <= VL_IDLE_UTIL_MAX) and (mem_free >= VL_MIN_MEM_FREE_GB) and (len(vl_queue) == 0)
    VL_IDLE_G.set(1 if idle else 0)
    VL_QUEUE_G.set(len(vl_queue))

    return idle


def is_deep(user_text: str) -> bool:
    """
    Heuristic to determine if query needs deeper model.

    Returns:
        True if query is complex/deep, False for simple queries
    """
    # Lightweight heuristic - can be replaced with real classifier later
    if len(user_text) > 180:
        return True

    deep_keywords = ["summarize", "explain", "steps", "analyze", "why", "compare", "describe", "detail"]
    return any(keyword in user_text.lower() for keyword in deep_keywords)


async def call_ollama_model(base_url: str, model: str, prompt: str, max_tokens: int = None, timeout_s: float = 30.0) -> str:
    """
    Call specific Ollama model at given base URL.

    Args:
        base_url: Ollama server URL
        model: Model name
        prompt: Complete prompt
        max_tokens: Optional token limit
        timeout_s: Request timeout in seconds

    Returns:
        Generated text response

    Raises:
        Exception on timeout or HTTP errors
    """
    payload = {"model": model, "prompt": prompt, "stream": False}
    if max_tokens:
        payload["options"] = {"num_predict": max_tokens}

    timeout = httpx.Timeout(connect=3.0, read=timeout_s, write=10.0, pool=3.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{base_url}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response") or data.get("text") or ""


async def route_and_generate(conv_id: str, prompt: str, user_text: str) -> str:
    """
    Intelligent routing: choose model based on complexity and GPU availability.

    Routing logic:
    1. Simple queries → Hermes3 (fast, 20s timeout)
    2. Deep queries + VL idle → VL model (opportunistic, 30s timeout)
    3. Deep queries + VL busy → Qwen3-4B fallback (25s timeout)
    4. Sticky sessions: keep using VL for N turns after first VL use

    Args:
        conv_id: Conversation ID for stickiness tracking
        prompt: Complete prompt with context
        user_text: Original user query (for complexity detection)

    Returns:
        Generated response text
    """
    now = time.time()

    # 1) Fast path for simple queries → Hermes3
    if not is_deep(user_text):
        try:
            ROUTE_FAST_HITS.inc()
            return await call_ollama_model(OLLAMA_TEXT_URL, TEXT_MODEL_FAST, prompt, max_tokens=384, timeout_s=20.0)
        except Exception as e:
            logger.warning(f"Hermes3 failed, fallback to 4B: {e}")
            # Fallthrough to 4B

    # 2) Sticky VL: if recently used VL successfully, try it again if idle
    if VL_TEXT_ENABLED and conv_sticky_until.get(conv_id, 0) > now and vl_idle():
        try:
            vl_queue.append(now)
            ROUTE_VL_HITS.inc()
            result = await call_ollama_model(OLLAMA_VL_URL, VL_MODEL, prompt, max_tokens=VL_TEXT_TOKEN_LIMIT, timeout_s=30.0)
            vl_queue.pop()
            conv_sticky_until[conv_id] = now + 600  # Extend stickiness 10 min
            return result
        except Exception as e:
            logger.warning(f"VL sticky failed: {e}")
            ROUTE_VL_FALLBACKS.inc()
            if vl_queue:
                vl_queue.pop()

    # 3) Opportunistic VL if idle
    if VL_TEXT_ENABLED and vl_idle():
        t0 = time.time()
        try:
            # Check queue wait budget
            queue_wait_ms = (time.time() - t0) * 1000
            if queue_wait_ms > VL_QUEUE_MAX_WAIT_MS:
                raise TimeoutError(f"VL queue wait {queue_wait_ms:.0f}ms exceeds budget")

            vl_queue.append(t0)
            ROUTE_VL_HITS.inc()
            result = await call_ollama_model(OLLAMA_VL_URL, VL_MODEL, prompt, max_tokens=VL_TEXT_TOKEN_LIMIT, timeout_s=30.0)
            conv_sticky_until[conv_id] = now + 600  # Start stickiness 10 min
            vl_queue.pop()
            return result
        except Exception as e:
            logger.warning(f"VL opportunistic failed: {e}")
            ROUTE_VL_FALLBACKS.inc()
            if vl_queue:
                vl_queue.pop()

    # 4) Deterministic fallback to Qwen3-4B
    try:
        ROUTE_4B_HITS.inc()
        return await call_ollama_model(OLLAMA_TEXT_URL, TEXT_MODEL, prompt, max_tokens=640, timeout_s=25.0)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e) or repr(e)}"
        logger.error(f"All models failed: {error_msg}", exc_info=True)
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
    conv_id = payload.get("conversation_id") or turn_id  # Allow client to pass stable conv ID
    logger.info(f"Chat request turn_id={turn_id} conv_id={conv_id[:8]}: {user_text[:50]}...")

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

    # --- LLM CALL (with intelligent routing) ---
    reply = await route_and_generate(conv_id, prompt, user_text)
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
