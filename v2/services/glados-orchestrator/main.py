"""
GLaDOS Orchestrator - Memory-aware chat service with intelligent routing
Step 2.5: Memory <-> LLM Integration
Step 2.6: VL Router - GPU-aware model selection
"""
"""
import os
import uuid
import time
import json
import hashlib
import logging
import threading
from typing import Any, Dict, List
from collections import defaultdict, deque

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Histogram, Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
import httpx

from background import Bg
from memory_client import MemoryClient
from memory_policy import worth_saving, redact, compute_hash
from nvml import sample_vl, get_gpu_info

os.umask(0o022)

# Inventory state (in-memory with file persistence)
STATE_DIR = "/app/state"
INVENTORY_SCHEMA_VERSION = 1
INVENTORY_FILE = os.path.join(STATE_DIR, "inventory.json")
inventory_lock = threading.Lock()
inventory_data = {
    "schema_version": INVENTORY_SCHEMA_VERSION,
    "items": {},
    "updated_at": None,
}

# Config state (in-memory)
config_state = {
    "privacy_pause": False,
    "energy_band": "medium",
    "focus_mode": "admin"
}

# Config metrics mapping
CONFIG_STATE_G = Gauge("orchestrator_config_state", "Configuration toggles (numeric)", ["key"])
ENERGY_BAND_VALUES = {"low": 0, "medium": 1, "high": 2}
FOCUS_MODE_VALUES = {"errands": 0, "admin": 1, "deep": 2}
VALID_ENERGY_BANDS = set(ENERGY_BAND_VALUES.keys())
VALID_FOCUS_MODES = set(FOCUS_MODE_VALUES.keys())

# Last reply cache for HA automations
last_reply_state: Dict[str, Any] = {"turn_id": None, "text": "", "when": None}

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

# Prometheus metrics - Vision ingest
VISION_EVENTS_TOTAL = Counter(
    "vision_events_ingested_total",
    "Vision events received from K80 router",
    ["source", "kind"],
)
PRIVACY_PAUSE_TOTAL = Counter(
    "orchestrator_privacy_paused_total",
    "Chat requests blocked by privacy pause",
)

# Router state
vl_queue = deque(maxlen=64)  # Lightweight queue tracker
conv_sticky_until = defaultdict(float)  # conv_id -> unix timestamp for VL stickiness
VISION_LOCK = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize app and services
app = FastAPI(title="glados-orchestrator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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


@app.get("/router/vision_lock")
async def vision_lock_state() -> JSONResponse:
    """Return current vision lock state (used by HA and the K80 router)."""
    return JSONResponse({"enabled": bool(VISION_LOCK)})


@app.post("/router/vision_lock")
async def vision_lock_toggle(payload: dict = Body(...)) -> JSONResponse:
    """
    Set or clear the vision lock flag.

    The K80 router flips this while escalating to VL so text routing can back off.
    """
    global VISION_LOCK
    enabled = bool(payload.get("enabled", True))
    VISION_LOCK = enabled
    logger.info("Vision lock %s", "enabled" if enabled else "cleared")
    return JSONResponse({"enabled": VISION_LOCK})


@app.post("/vision/event")
async def vision_event(event: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Receive unified vision events from the K80 router and persist compact memories.
    """
    source = (event.get("source") or "unknown").lower()
    vl_payload = event.get("vl")
    has_summary = isinstance(vl_payload, dict) and bool(vl_payload.get("summary"))
    memory_kind = "vision_event"
    if source == "screen":
        memory_kind = "screen_ocr"
    if has_summary:
        memory_kind = "screen_summary"

    VISION_EVENTS_TOTAL.labels(source=source, kind=memory_kind).inc()

    turn_id = event.get("id") or str(uuid.uuid4())
    text_blob = _format_vision_memory(event)

    if text_blob:
        bg.spawn(
            mem.add(
                text=text_blob,
                turn_id=turn_id,
                role="system",
                ctx_hits=0,
                kind=memory_kind,
                source="vision-router",
            ),
            name=f"vision_event_{turn_id[:8]}",
        )

    return JSONResponse({"ok": True})


# ===== Inventory Endpoints =====

@app.get("/inventory/snapshot")
async def inventory_snapshot() -> JSONResponse:
    """
    Return current inventory snapshot.

    Returns:
        - count: Number of items
        - items: Dict of item_name -> {quantity, unit, location, ...}
        - updated_at: ISO timestamp of last update
    """
    with inventory_lock:
        snapshot = {
            "schema_version": inventory_data.get("schema_version", INVENTORY_SCHEMA_VERSION),
            "count": len(inventory_data["items"]),
            "items": inventory_data["items"],
            "updated_at": inventory_data["updated_at"] or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    return JSONResponse(snapshot)


@app.post("/inventory/upsert")
async def inventory_upsert(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Update or insert inventory item.

    Request body:
        - name: Item name (required)
        - quantity: Number (default 1)
        - unit: Unit string (default "count")
        - location: Storage location (optional)
        - notes: Additional notes (optional)
    """
    item_name = str(payload.get("name", "")).strip()
    if not item_name:
        return JSONResponse({"error": "name required"}, status_code=400)

    with inventory_lock:
        existing = inventory_data["items"].get(item_name, {})
        quantity = payload.get("quantity", payload.get("qty", existing.get("quantity", 1)))
        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            quantity = existing.get("quantity", 1)

        if isinstance(quantity, float) and quantity.is_integer():
            quantity = int(quantity)

        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        inventory_data["items"][item_name] = {
            "name": item_name,
            "quantity": quantity,
            "unit": payload.get("unit", existing.get("unit", "count")),
            "location": payload.get("location", existing.get("location", "unknown")),
            "notes": payload.get("notes", existing.get("notes", "")),
            "updated_at": timestamp,
        }
        inventory_data["updated_at"] = timestamp
        inventory_data["schema_version"] = INVENTORY_SCHEMA_VERSION
        item_snapshot = dict(inventory_data["items"][item_name])

    # Persist to file (fire-and-forget)
    bg.spawn(_save_inventory(), name="save_inventory")

    logger.info(f"Inventory updated: {item_name} = {item_snapshot}")
    return JSONResponse({"ok": True, "item": item_name})


@app.post("/inventory/sync_json")
async def inventory_sync_json(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Bulk sync inventory from HA JSON sensor.

    Request body:
        - items: Dict or list of inventory items
    """
    incoming_items = payload.get("items", {})
    sanitized: Dict[str, Any] = {}

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if isinstance(incoming_items, dict):
        for raw_name, raw_entry in incoming_items.items():
            name = str(raw_name or "").strip()
            if not name:
                continue
            entry = dict(raw_entry) if isinstance(raw_entry, dict) else {"quantity": raw_entry}
            quantity = entry.get("quantity", entry.get("qty", entry.get("count", 1)))
            try:
                quantity = float(quantity)
            except (TypeError, ValueError):
                quantity = 1
            if isinstance(quantity, float) and quantity.is_integer():
                quantity = int(quantity)
            sanitized[name] = {
                "name": name,
                "quantity": quantity,
                "unit": entry.get("unit", entry.get("units", "count")),
                "location": entry.get("location", entry.get("zone", "unknown")),
                "notes": entry.get("notes", entry.get("description", "")),
                "updated_at": entry.get("updated_at") or now,
            }
    elif isinstance(incoming_items, list):
        for entry in incoming_items:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            quantity = entry.get("quantity", entry.get("qty", entry.get("count", 1)))
            try:
                quantity = float(quantity)
            except (TypeError, ValueError):
                quantity = 1
            if isinstance(quantity, float) and quantity.is_integer():
                quantity = int(quantity)
            sanitized[name] = {
                "name": name,
                "quantity": quantity,
                "unit": entry.get("unit", entry.get("units", "count")),
                "location": entry.get("location", entry.get("zone", "unknown")),
                "notes": entry.get("notes", entry.get("description", "")),
                "updated_at": entry.get("updated_at") or now,
            }
    else:
        return JSONResponse({"error": "items must be dict or list"}, status_code=400)

    with inventory_lock:
        inventory_data["items"] = sanitized
        inventory_data["updated_at"] = now
        inventory_data["schema_version"] = INVENTORY_SCHEMA_VERSION

    # Persist to file (fire-and-forget)
    bg.spawn(_save_inventory(), name="save_inventory")

    logger.info(f"Inventory synced: {len(sanitized)} items")
    return JSONResponse({"ok": True, "count": len(sanitized)})


async def _save_inventory():
    """Persist inventory to file"""
    try:
        with inventory_lock:
            snapshot = json.loads(json.dumps(inventory_data))

        os.makedirs(STATE_DIR, exist_ok=True)
        tmp_path = f"{INVENTORY_FILE}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, INVENTORY_FILE)
        os.chmod(INVENTORY_FILE, 0o644)
    except Exception as e:
        logger.error(f"Failed to save inventory: {e}")
        tmp_path = f"{INVENTORY_FILE}.tmp"
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


def _update_config_metrics() -> None:
    """Refresh Prometheus gauges for configuration state."""
    CONFIG_STATE_G.labels(key="privacy_pause").set(1 if config_state["privacy_pause"] else 0)
    CONFIG_STATE_G.labels(key="energy_band").set(ENERGY_BAND_VALUES.get(config_state["energy_band"], 1))
    CONFIG_STATE_G.labels(key="focus_mode").set(FOCUS_MODE_VALUES.get(config_state["focus_mode"], 1))


_update_config_metrics()


# ===== Config Endpoint =====

@app.get("/config")
async def get_config() -> JSONResponse:
    """Get current configuration state"""
    return JSONResponse(config_state)


@app.post("/config")
async def set_config(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Update configuration state.

    Accepts partial updates for:
        - privacy_pause: bool
        - energy_band: "low" | "medium" | "high"
        - focus_mode: "deep" | "admin" | "errands"
    """
    updated = False

    if "privacy_pause" in payload:
        config_state["privacy_pause"] = bool(payload["privacy_pause"])
        logger.info(f"Privacy pause: {config_state['privacy_pause']}")
        updated = True

    if "energy_band" in payload:
        band = str(payload["energy_band"]).lower()
        if band not in VALID_ENERGY_BANDS:
            return JSONResponse({"error": f"invalid energy_band '{band}'"}, status_code=400)
        config_state["energy_band"] = band
        logger.info(f"Energy band: {config_state['energy_band']}")
        updated = True

    if "focus_mode" in payload:
        mode = str(payload["focus_mode"]).lower()
        if mode not in VALID_FOCUS_MODES:
            return JSONResponse({"error": f"invalid focus_mode '{mode}'"}, status_code=400)
        config_state["focus_mode"] = mode
        logger.info(f"Focus mode: {config_state['focus_mode']}")
        updated = True

    if updated:
        _update_config_metrics()

    return JSONResponse(config_state)


@app.get("/last_reply")
async def last_reply() -> JSONResponse:
    """Expose last chat reply for Home Assistant automations."""
    return JSONResponse(last_reply_state)


# ===== Calendar Mirror Endpoint =====

@app.post("/calendar/mirror")
async def calendar_mirror(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Mirror calendar event from work to personal.

    Request body:
        - summary: Event title
        - start: Start time (ISO format)
        - end: End time (ISO format)

    Currently a stub - logs the event and returns success.
    Will be connected to HA calendar webhook in future.
    """
    summary = payload.get("summary", "Unknown")
    start = payload.get("start", "")
    end = payload.get("end", "")

    logger.info(f"Calendar mirror: {summary} ({start} -> {end})")

    # Future: POST to HA calendar service or webhook
    # For now, just log and return success

    return JSONResponse({"ok": True, "event": summary})


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
    if VISION_LOCK:
        idle = False
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


def _format_vision_memory(event: Dict[str, Any]) -> str:
    """Build a compact textual representation of a vision event for memory storage."""
    if not isinstance(event, dict):
        return ""

    source = event.get("source", "unknown")
    score = event.get("score")
    tags: List[str] = []
    detections: List[Dict[str, Any]] = []

    k80_payload = event.get("k80") or {}
    if isinstance(k80_payload, dict):
        tags = list(k80_payload.get("tags") or [])
        detections = list(k80_payload.get("detections") or [])

    # Fall back to top-level tags/detections if present
    if not tags:
        tags = list(event.get("tags") or [])
    if not detections:
        detections = list(event.get("detections") or [])

    headline = f"[Vision] source={source}"
    if isinstance(score, (int, float)):
        headline += f" score={score:.2f}"
    elif score is not None:
        headline += f" score={score}"

    lines = [headline]
    if tags:
        lines.append("tags: " + ", ".join(str(tag) for tag in tags[:8]))

    det_labels = sorted(
        {str(det.get("label")) for det in detections if isinstance(det, dict) and det.get("label")}
    )
    if det_labels:
        lines.append("detections: " + ", ".join(det_labels[:6]))

    vl_payload = event.get("vl")
    summary_text = None
    bullet_points: List[str] = []
    if isinstance(vl_payload, dict):
        summary_text = vl_payload.get("summary") or vl_payload.get("text")
        raw_bullets = vl_payload.get("bullets") or []
        bullet_points = [str(item) for item in raw_bullets if isinstance(item, str)]

    if summary_text:
        lines.append("summary: " + summary_text)
    if bullet_points:
        lines.extend(f"- {bullet}" for bullet in bullet_points[:5])

    if not summary_text:
        frames: List[Dict[str, Any]] = []
        if isinstance(k80_payload, dict):
            frames = list(k80_payload.get("frames") or [])
        if not frames:
            frames = list(event.get("frames") or [])

        for frame in frames:
            if not isinstance(frame, dict):
                continue
            ocr = frame.get("ocr") or {}
            if not isinstance(ocr, dict):
                continue
            text = ocr.get("text")
            if text:
                lines.append("ocr: " + str(text)[:300])
                break

    text_blob = "\n".join(lines).strip()
    return text_blob[:4000]


async def route_and_generate(conv_id: str, prompt: str, user_text: str) -> str:
    """
    Intelligent routing: choose model based on complexity and GPU availability.

    Routing logic:
    1. Simple queries -> Hermes3 (fast, 20s timeout)
    2. Deep queries + VL idle -> VL model (opportunistic, 30s timeout)
    3. Deep queries + VL busy -> Qwen3-4B fallback (25s timeout)
    4. Sticky sessions: keep using VL for N turns after first VL use

    Args:
        conv_id: Conversation ID for stickiness tracking
        prompt: Complete prompt with context
        user_text: Original user query (for complexity detection)

    Returns:
        Generated response text
    """
    now = time.time()

    # 1) Fast path for simple queries -> Hermes3
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

    Step 2.5: Pre-retrieval -> context injection -> LLM -> post-storage

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

    if config_state.get("privacy_pause"):
        reply = "Privacy pause is active. No processing performed."
        last_reply_state.update(
            {
                "turn_id": turn_id,
                "text": reply,
                "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        PRIVACY_PAUSE_TOTAL.inc()
        logger.info("Privacy pause active; dropping chat request.")
        return JSONResponse({
            "turn_id": turn_id,
            "reply": reply,
            "memory_hits": 0,
            "ctx_chars": 0,
            "privacy_pause": True
        })

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

    response_payload = {
        "turn_id": turn_id,
        "reply": reply,
        "memory_hits": len(hits),
        "ctx_chars": len(ctx)
    }
    last_reply_state.update(
        {
            "turn_id": turn_id,
            "text": reply,
            "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )

    return JSONResponse(response_payload)


@app.post("/v1/chat/completions")
async def openai_chat_completions(payload: Dict = Body(...)) -> JSONResponse:
    """
    OpenAI-compatible chat completions endpoint for Home Assistant integration.

    Step 2.7: Assist -> Orchestrator Bridge

    Accepts OpenAI format and forwards to /chat endpoint with memory integration.

    Request body (OpenAI format):
        - model: Model name (ignored, we use intelligent routing)
        - messages: Array of {role, content} objects
        - stream: Boolean (currently only supports false)

    Returns OpenAI format:
        - id: Turn ID
        - object: "chat.completion"
        - created: Unix timestamp
        - model: Model used
        - choices: Array with message and finish_reason
    """
    # Extract messages
    messages = payload.get("messages", [])
    if not messages:
        return JSONResponse(
            {"error": {"message": "messages required", "type": "invalid_request_error"}},
            status_code=400
        )

    # Find last user message
    user_message = None
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            user_message = msg.get("content", "").strip()
            break

    if not user_message:
        return JSONResponse(
            {"error": {"message": "No user message found", "type": "invalid_request_error"}},
            status_code=400
        )

    # Extract conversation_id from messages (use first message's content hash as stable ID)
    # This ensures multi-turn conversations maintain VL stickiness
    conv_id = None
    if len(messages) > 1:
        # Use hash of first user message as stable conversation ID
        first_user_msg = next((m.get("content") for m in messages if m.get("role") == "user"), None)
        if first_user_msg:
            conv_id = hashlib.sha256(first_user_msg.encode()).hexdigest()[:16]

    # Call internal /chat endpoint
    chat_payload = {
        "input": user_message,
        "conversation_id": conv_id
    }

    # Check for system message override
    system_msg = next((m.get("content") for m in messages if m.get("role") == "system"), None)
    if system_msg:
        chat_payload["system_prompt"] = system_msg

    # Make internal call to /chat
    result = await chat(chat_payload)
    result_data = result.body.decode() if hasattr(result, 'body') else '{}'

    # Parse result
    try:
        chat_response = json.loads(result_data)
    except:
        chat_response = {"reply": "Error processing response"}

    reply_text = chat_response.get("reply", "")
    turn_id = chat_response.get("turn_id", str(uuid.uuid4()))

    # Build OpenAI-compatible response
    openai_response = {
        "id": f"chatcmpl-{turn_id[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": payload.get("model", "glados-orchestrator"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": reply_text
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": len(user_message.split()),
            "completion_tokens": len(reply_text.split()),
            "total_tokens": len(user_message.split()) + len(reply_text.split())
        }
    }

    logger.info(f"OpenAI API call completed: turn_id={turn_id}, memory_hits={chat_response.get('memory_hits', 0)}")

    return JSONResponse(openai_response)


@app.on_event("startup")
async def startup_event():
    """Load inventory from file on startup"""
    global inventory_data
    _update_config_metrics()
    if os.path.exists(INVENTORY_FILE):
        try:
            with open(INVENTORY_FILE, "r") as f:
                data = json.load(f)

            raw_items = data.get("items", {})
            normalized: Dict[str, Any] = {}

            if isinstance(raw_items, dict):
                iterable = raw_items.items()
            elif isinstance(raw_items, list):
                iterable = [
                    (entry.get("name"), entry)
                    for entry in raw_items
                    if isinstance(entry, dict)
                ]
            else:
                iterable = []

            for raw_name, raw_entry in iterable:
                name = str(raw_name or "").strip()
                if not name:
                    continue
                entry = dict(raw_entry) if isinstance(raw_entry, dict) else {"quantity": raw_entry}
                quantity = entry.get("quantity", entry.get("qty", entry.get("count", 1)))
                try:
                    quantity = float(quantity)
                except (TypeError, ValueError):
                    quantity = 1
                if isinstance(quantity, float) and quantity.is_integer():
                    quantity = int(quantity)

                normalized[name] = {
                    "name": name,
                    "quantity": quantity,
                    "unit": entry.get("unit", entry.get("units", "count")),
                    "location": entry.get("location", entry.get("zone", "unknown")),
                    "notes": entry.get("notes", entry.get("description", "")),
                    "updated_at": entry.get("updated_at") or data.get("updated_at") or now,
                }

            inventory_data = {
                "schema_version": data.get("schema_version", INVENTORY_SCHEMA_VERSION),
                "items": normalized,
                "updated_at": data.get("updated_at"),
            }

            logger.info(f"Loaded inventory: {len(normalized)} items")
        except Exception as e:
            logger.warning(f"Failed to load inventory: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down orchestrator...")
    # Background tasks will be cancelled automatically
