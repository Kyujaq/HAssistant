"""
GLaDOS Orchestrator - Memory-aware chat service with intelligent routing
Step 2.5: Memory <-> LLM Integration
Step 2.6: VL Router - GPU-aware model selection
"""
import asyncio
from contextlib import suppress
import os
import uuid
import time
import json
import hashlib
import logging
import threading
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from collections import defaultdict, deque

from fastapi import FastAPI, Body, HTTPException
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
    "focus_mode": "admin",
    "vision_tts_notify": False,
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

# Vision configuration (K80 VM services)
VISION_ROUTER_URL = os.getenv("VISION_ROUTER_URL", "http://192.168.122.71:8050")
VISION_GATEWAY_URL = os.getenv("VISION_GATEWAY_URL", "http://192.168.122.71:8051")
VISION_ENABLED = os.getenv("VISION_ENABLED", "1") == "1"  # Enable/disable vision context
VISION_TIMEOUT_S = float(os.getenv("VISION_TIMEOUT_S", "3.0"))

# Realtime streaming configuration
REALTIME_STREAM_ENABLED = os.getenv("ENABLE_REALTIME_STREAMING", "0") == "1"
PIPELINE_REALTIME_URL = os.getenv("PIPELINE_REALTIME_URL", "")
REALTIME_FLUSH_MARKERS = os.getenv("REALTIME_FLUSH_MARKERS", ".?!\n")
REALTIME_CONNECT_TIMEOUT = float(os.getenv("REALTIME_CONNECT_TIMEOUT", "2.0"))
REALTIME_READ_TIMEOUT = float(os.getenv("REALTIME_READ_TIMEOUT", "30.0"))
REALTIME_SESSION_TTL = float(os.getenv("REALTIME_SESSION_TTL", "30.0"))
REALTIME_SAMPLE_RATE_DEFAULT = int(os.getenv("REALTIME_SAMPLE_RATE", "22050"))

HA_BASE_URL = os.getenv("HA_BASE_URL")
HA_TOKEN = os.getenv("HA_TOKEN")
HA_EVENT_TIMEOUT = float(os.getenv("HA_EVENT_TIMEOUT", "5.0"))

# Vision router configuration
VISION_ROUTER_URL = os.getenv("VISION_ROUTER_URL", "http://vision-router:8050")

# Router configuration
VL_IDLE_UTIL_MAX = float(os.getenv("VL_IDLE_UTIL_MAX", "0.50"))
VL_MIN_MEM_FREE_GB = float(os.getenv("VL_MIN_MEM_FREE_GB", "3.0"))
VL_QUEUE_MAX_WAIT_MS = int(os.getenv("VL_QUEUE_MAX_WAIT_MS", "400"))
VL_TEXT_ENABLED = os.getenv("VL_TEXT_ENABLED", "1") == "1"
VL_STICKY_TURNS_MIN = max(1, int(os.getenv("VL_STICKY_TURNS_MIN", "5")))
VL_STICKY_WINDOW_S = int(os.getenv("VL_STICKY_WINDOW_S", "600"))
VL_TEXT_TOKEN_LIMIT = int(os.getenv("VL_TEXT_TOKEN_LIMIT", "768"))

# Prometheus metrics - Memory
PRE_MS = Histogram("orchestrator_memory_pre_ms", "Pre-retrieval latency (ms)")
POST_MS = Histogram("orchestrator_memory_post_ms", "Post-storage latency (ms)")
CTX_CHARS = Histogram("orchestrator_ctx_chars", "Context characters injected")

# Realtime session cache
REALTIME_SESSION_CACHE: Dict[str, Dict[str, Any]] = {}
REALTIME_SESSION_CACHE_LOCK = asyncio.Lock()


async def _register_realtime_session(
    text: str,
    session_id: str,
    voice: Optional[str],
    sample_rate: Optional[int] = None,
) -> None:
    if not text or not session_id:
        return
    now = time.time()
    resolved_rate = REALTIME_SAMPLE_RATE_DEFAULT
    if sample_rate is not None:
        try:
            resolved_rate = max(8000, int(sample_rate))
        except (TypeError, ValueError):
            resolved_rate = REALTIME_SAMPLE_RATE_DEFAULT
    entry = {
        "session_id": session_id,
        "voice": voice,
        "realtime_url": PIPELINE_REALTIME_URL,
        "sample_rate": resolved_rate,
        "expires": now + REALTIME_SESSION_TTL,
    }
    aliases = {text}
    stripped = text.strip()
    if stripped and stripped != text:
        aliases.add(stripped)
    entry["_aliases"] = list(aliases)
    async with REALTIME_SESSION_CACHE_LOCK:
        for key, cached in list(REALTIME_SESSION_CACHE.items()):
            if cached.get("expires", 0) < now:
                REALTIME_SESSION_CACHE.pop(key, None)
        for key in aliases:
            REALTIME_SESSION_CACHE[key] = entry


async def _claim_realtime_session(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    now = time.time()
    aliases = [text, text.strip()]
    async with REALTIME_SESSION_CACHE_LOCK:
        entry = None
        for key in aliases:
            if not key:
                continue
            candidate = REALTIME_SESSION_CACHE.get(key)
            if candidate:
                entry = candidate
                break
        if entry is None:
            return None
        if entry.get("expires", 0) < now:
            for alias in entry.get("_aliases", []):
                REALTIME_SESSION_CACHE.pop(alias, None)
            return None
        # Remove all aliases
        for alias in entry.get("_aliases", []):
            REALTIME_SESSION_CACHE.pop(alias, None)
    result = dict(entry)
    result.pop("_aliases", None)
    return result

# Prometheus metrics - Router
ROUTE_VL_HITS = Counter("route_vl_text_hits", "Text queries routed to VL", ["source"])
ROUTE_VL_FALLBACKS = Counter("route_vl_text_fallbacks", "VL text fallbacks to 4B", ["source"])
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
    ["stage", "source", "kind"],
)
VISION_STAGE_TOTAL = Counter(
    "vision_events_stage_total",
    "Vision events by stage",
    ["stage"],
)
VISION_VL_USED_TOTAL = Counter(
    "vision_vl_used_total",
    "Vision events with VL summaries",
)
PRIVACY_PAUSE_TOTAL = Counter(
    "orchestrator_privacy_paused_total",
    "Chat requests blocked by privacy pause",
)

# Router state
vl_queue = deque(maxlen=64)  # Lightweight queue tracker
conv_sticky_until = defaultdict(float)  # conv_id -> unix timestamp for VL stickiness
conv_vl_history = defaultdict(lambda: deque(maxlen=VL_STICKY_TURNS_MIN))
VISION_LOCK = False
VISION_EVENT_HISTORY_MAX = 2048
VISION_EVENT_HISTORY = defaultdict(deque)
VISION_EVENT_SEEN = defaultdict(set)
VISION_RECENT_VL = deque(maxlen=10)

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

_HA_GROCERY_KEYWORDS = {
    "grocery",
    "groceries",
    "inventory",
    "pantry",
    "fridge",
    "food",
    "kitchen",
}


async def _ha_fire_event(event_type: str, payload: Dict[str, Any]) -> None:
    if not HA_BASE_URL or not HA_TOKEN:
        return
    base = HA_BASE_URL.rstrip("/")
    timeout = httpx.Timeout(HA_EVENT_TIMEOUT, read=HA_EVENT_TIMEOUT)
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            await client.post(f"{base}/api/events/{event_type}", json=payload, headers=headers)
    except Exception as exc:
        logger.warning("Failed to post HA event %s: %s", event_type, exc)


def _should_emit_grocery_event(
    tags: List[str], detections: List[Dict[str, Any]], meta: Dict[str, Any]
) -> bool:
    lowered_tags = {tag.lower() for tag in tags}
    if _HA_GROCERY_KEYWORDS.intersection(lowered_tags):
        return True

    for detection in detections:
        label = str(detection.get("label", "")).lower()
        if label in {"product", "grocery", "food", "item"}:
            return True

    meta_task = str(meta.get("task", "")).lower()
    if meta_task and any(keyword in meta_task for keyword in _HA_GROCERY_KEYWORDS):
        return True

    meta_kind = str(meta.get("kind", "")).lower()
    if meta_kind and any(keyword in meta_kind for keyword in _HA_GROCERY_KEYWORDS):
        return True

    return False


def _extract_primary_frame(frames: List[Dict[str, Any]]) -> Optional[str]:
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        url = frame.get("url")
        if url:
            return str(url)
    return None


# ===== Vision Context Helper =====

async def _fetch_vision_context(user_query: str) -> Optional[str]:
    """
    Fetch latest vision analysis from K80 VM if user query is vision-related.

    Returns:
        Vision summary string if available, None otherwise
    """
    if not VISION_ENABLED:
        return None

    # Detect vision-related keywords
    query_lower = user_query.lower()
    vision_keywords = [
        "screen", "display", "monitor", "see", "looking at", "desktop",
        "camera", "door", "window", "application", "app", "program",
        "what's on", "whats on", "show me", "visible", "view"
    ]

    if not any(keyword in query_lower for keyword in vision_keywords):
        return None

    logger.info("Vision query detected, fetching latest analysis from K80 VM")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(VISION_TIMEOUT_S)) as client:
            # Try to get recent VL summary from vision-router stats
            # This checks if there are any recent high-confidence vision events
            stats_resp = await client.get(f"{VISION_ROUTER_URL}/stats")
            if stats_resp.status_code == 200:
                stats = stats_resp.json()
                # Check if we have recent VL summaries in VISION_RECENT_VL deque
                if VISION_RECENT_VL:
                    latest_vl = VISION_RECENT_VL[-1]  # Most recent
                    if time.time() - latest_vl.get("timestamp", 0) < 60:  # < 1 min old
                        summary = latest_vl.get("summary", "")
                        if summary:
                            logger.info(f"Using cached VL summary: {summary[:100]}...")
                            return summary

            # No recent cache, trigger fresh analysis via vision-gateway
            # Note: This is a simple implementation - more sophisticated would be:
            # 1. Check scene has changed (motion detection)
            # 2. Use vision-router /analyze endpoint
            # For now, just log that we'd fetch vision but return None
            logger.info("No recent vision cache available. Consider calling vision-router /analyze.")
            return None

    except Exception as e:
        logger.warning(f"Vision context fetch failed: {e}")
        return None


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
async def vision_event(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """Handle pre/post vision events from the router with deduping and memory storage."""

    raw_stage = payload.get("stage")
    event_payload = payload.get("event")
    event: Dict[str, Any]
    if raw_stage is None and not isinstance(event_payload, dict):
        stage = "post"
        event = {k: v for k, v in payload.items() if k != "event"}
    else:
        stage = str(raw_stage or "post").lower()
        if isinstance(event_payload, dict):
            event = dict(event_payload)
        else:
            event = {k: v for k, v in payload.items() if k != "event"}
    if stage not in {"pre", "post"}:
        raise HTTPException(status_code=400, detail="stage must be 'pre' or 'post'")

    turn_id_value = payload.get("turn_id") or event.get("turn_id")
    turn_id = str(turn_id_value) if turn_id_value else str(uuid.uuid4())
    event.setdefault("turn_id", turn_id)

    meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
    conv_id_value = payload.get("conversation_id") or meta.get("conversation_id")
    conv_id = str(conv_id_value) if conv_id_value else turn_id
    event.setdefault("conversation_id", conv_id)
    event.setdefault("stage", stage)

    event_without_id = {k: v for k, v in event.items() if k != "id"}
    existing_event_id = event.get("id")
    if existing_event_id:
        event_id = str(existing_event_id)
    else:
        event_id = _stable_event_id(stage, turn_id, event_without_id)
    event["id"] = event_id

    if not _record_vision_event(stage, event_id):
        return JSONResponse(
            {
                "turn_id": turn_id,
                "stage": stage,
                "event_id": event_id,
                "duplicate": True,
                "conversation_id": conv_id,
            }
        )

    source = (event.get("source") or "unknown").lower()
    vl_payload_raw = event.get("vl")
    vl_payload = vl_payload_raw if isinstance(vl_payload_raw, dict) else None

    tags: List[str] = []
    raw_tags = event.get("tags")
    if isinstance(raw_tags, list):
        for tag in raw_tags:
            if isinstance(tag, (str, int, float)):
                tags.append(str(tag))

    k80_payload_raw = event.get("k80")
    k80_payload = k80_payload_raw if isinstance(k80_payload_raw, dict) else {}
    k80_tags = list(k80_payload.get("tags") or [])
    k80_detections: List[Dict[str, Any]] = list(k80_payload.get("detections") or [])
    k80_meta: Dict[str, Any] = dict(k80_payload.get("meta") or {})
    k80_frames: List[Dict[str, Any]] = list(k80_payload.get("frames") or [])

    for tag in k80_tags:
        if isinstance(tag, (str, int, float)):
            tags.append(str(tag))

    # Deduplicate tags while keeping order
    seen_tags: Set[str] = set()
    deduped_tags: List[str] = []
    for tag in tags:
        if tag not in seen_tags:
            seen_tags.add(tag)
            deduped_tags.append(tag)

    if not k80_detections:
        k80_detections = list(event.get("detections") or [])

    top_level_meta = event.get("meta")
    combined_meta: Dict[str, Any] = dict(k80_meta)
    if isinstance(top_level_meta, dict):
        combined_meta.update(top_level_meta)

    if not k80_frames:
        k80_frames = list(event.get("frames") or [])

    memory_kind = "vision_pre" if stage == "pre" else "vision_post"
    VISION_EVENTS_TOTAL.labels(stage=stage, source=source, kind=memory_kind).inc()
    VISION_STAGE_TOTAL.labels(stage=stage).inc()

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
            name=f"vision_{stage}_{turn_id[:8]}",
        )

    response: Dict[str, Any] = {
        "turn_id": turn_id,
        "stage": stage,
        "event_id": event_id,
        "duplicate": False,
        "conversation_id": conv_id,
    }

    summary = _extract_vl_summary(vl_payload) if stage == "post" else ""
    sticky_until = conv_sticky_until.get(conv_id, 0.0)
    vl_used = False

    if stage == "post":
        vl_used = bool(summary)
        history = conv_vl_history[conv_id]
        history.append(vl_used)
        VISION_RECENT_VL.append(
            {"conv_id": conv_id, "turn_id": turn_id, "used_vl": vl_used, "ts": time.time()}
        )

        if vl_used:
            VISION_VL_USED_TOTAL.inc()
            if len(history) >= VL_STICKY_TURNS_MIN and all(history):
                sticky_until = time.time() + VL_STICKY_WINDOW_S
                conv_sticky_until[conv_id] = sticky_until
        if sticky_until:
            conv_sticky_until[conv_id] = sticky_until
            response["sticky_until"] = sticky_until

        response["vl_used"] = vl_used
        if vl_used:
            response["vl_summary"] = summary
            notification_text = _build_vision_notification(summary, source, deduped_tags)
            if notification_text:
                response["vl_notification"] = notification_text
                if config_state.get("vision_tts_notify"):
                    bg.spawn(_vision_tts_notify(notification_text), name=f"vision_tts_{turn_id[:8]}")

        ha_payload: Dict[str, Any] = {
            "event_id": event_id,
            "turn_id": turn_id,
            "source": source,
            "score": event.get("score"),
            "tags": deduped_tags,
            "detections": k80_detections,
            "meta": combined_meta,
            "vl_summary": summary,
            "vl_used": vl_used,
            "ts": event.get("ts"),
        }

        primary_frame = _extract_primary_frame(k80_frames)
        if not primary_frame:
            primary_frame = _extract_primary_frame(event.get("frames") or [])
        if primary_frame:
            ha_payload["frame"] = primary_frame

        bg.spawn(
            _ha_fire_event("vision_router.event", ha_payload),
            name=f"ha_vision_event_{event_id[:8]}",
        )

        if _should_emit_grocery_event(deduped_tags, k80_detections, combined_meta):
            bg.spawn(
                _ha_fire_event("vision_router.grocery_detected", ha_payload),
                name=f"ha_grocery_event_{event_id[:8]}",
            )

    return JSONResponse(response)


@app.get("/vision/config")
async def vision_config_get() -> JSONResponse:
    router_config: Dict[str, Any]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, read=5.0)) as client:
            response = await client.get(f"{VISION_ROUTER_URL}/config")
            response.raise_for_status()
            router_config = response.json()
    except Exception as exc:
        router_config = {"error": str(exc)}

    return JSONResponse(
        {
            "local": {"vision_tts_notify": config_state.get("vision_tts_notify", False)},
            "router": router_config,
        }
    )


@app.post("/vision/config")
async def vision_config_set(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    result: Dict[str, Any] = {"local": {}, "router": {}}

    if "vision_tts_notify" in payload:
        config_state["vision_tts_notify"] = bool(payload["vision_tts_notify"])
        _update_config_metrics()
        result["local"]["vision_tts_notify"] = config_state["vision_tts_notify"]

    router_payload: Dict[str, Any] = {}
    if "vision_on" in payload:
        router_payload["vision_on"] = bool(payload["vision_on"])
    if "screen_watch_on" in payload:
        router_payload["screen_watch_on"] = bool(payload["screen_watch_on"])
    if "threshold" in payload:
        router_payload["threshold"] = float(payload["threshold"])
    if "max_frames" in payload:
        router_payload["max_frames"] = int(payload["max_frames"])

    if router_payload:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, read=5.0)) as client:
                response = await client.post(f"{VISION_ROUTER_URL}/config", json=router_payload)
                response.raise_for_status()
                result["router"] = response.json()
        except Exception as exc:
            result["router"] = {"error": str(exc)}

    return JSONResponse(result)


@app.post("/vision/vl_summarize")
async def vision_vl_summarize(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    VL summarization endpoint for K80 vision-router.

    Receives a bundle with frames/OCR and generates vision-language captions.

    Request body:
        - source: Event source (screen/frigate/etc)
        - frames: List of {url, ocr} frame objects
        - hints: {ocr_text, tags, detections}
        - task: Task type (meeting/generic)
        - ts: Timestamp
        - meta: Additional metadata

    Returns:
        - summary: Text summary of the visual content
        - captions: List of per-frame captions (optional)
        - error: Error message if VL fails
    """
    source = payload.get("source", "unknown")
    frames = payload.get("frames") or []
    hints = payload.get("hints") or {}
    task = payload.get("task", "generic")

    # Build prompt for VL model
    ocr_text = (hints.get("ocr_text") or "").strip()
    tags = hints.get("tags") or []
    detections = hints.get("detections") or []

    # Construct vision prompt
    prompt_parts = []

    if task == "meeting":
        prompt_parts.append("Analyze this presentation/meeting slide:")
    else:
        prompt_parts.append("Describe what you see in this image:")

    if ocr_text:
        prompt_parts.append(f"\nExtracted text: {ocr_text[:1000]}")

    if tags:
        prompt_parts.append(f"\nContext tags: {', '.join(str(t) for t in tags[:5])}")

    if detections:
        det_labels = [str(d.get("label")) for d in detections if isinstance(d, dict) and d.get("label")]
        if det_labels:
            prompt_parts.append(f"\nDetected objects: {', '.join(det_labels[:5])}")

    prompt_parts.append("\n\nProvide a concise 2-3 sentence summary focusing on the key information and actionable items.")

    vision_prompt = "\n".join(prompt_parts)

    # For now, use text-only VL call since we don't have image URLs accessible
    # In future, this would fetch image data and send to VL model with vision capabilities
    # Current limitation: Ollama VL requires actual image data, not URLs

    try:
        # Call VL model with text prompt (will be enhanced with actual vision when image fetch is added)
        t0 = time.time()

        # Check if VL is available
        util, mem_free = sample_vl()
        if util > 0.60 or mem_free < VL_MIN_MEM_FREE_GB:
            # Hard fallback: GPU util > 60% -> use qwen3:4b instead
            logger.warning(f"VL GPU busy (util={util:.2f}, mem_free={mem_free:.2f}GB), using 4B fallback")
            ROUTE_VL_FALLBACKS.labels(source="vision").inc()
            summary = await call_ollama_model(
                OLLAMA_TEXT_URL,
                TEXT_MODEL,
                f"Summarize this visual content:\n{vision_prompt}",
                max_tokens=512,
                timeout_s=25.0
            )
        else:
            # Use VL model
            vl_queue.append(t0)
            ROUTE_VL_HITS.labels(source="vision").inc()
            summary = await call_ollama_model(
                OLLAMA_VL_URL,
                VL_MODEL,
                vision_prompt,
                max_tokens=512,
                timeout_s=30.0
            )
            if vl_queue:
                vl_queue.pop()

        latency_ms = (time.time() - t0) * 1000
        logger.info(f"VL summarize: {source} task={task} {latency_ms:.1f}ms")

        return JSONResponse({
            "summary": summary.strip(),
            "source": source,
            "task": task,
            "latency_ms": round(latency_ms, 1)
        })

    except Exception as exc:
        if vl_queue:
            vl_queue.pop()
        ROUTE_VL_FALLBACKS.labels(source="vision").inc()
        logger.error(f"VL summarize failed: {exc}")
        return JSONResponse({
            "error": str(exc),
            "source": source,
            "task": task
        }, status_code=500)


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
    CONFIG_STATE_G.labels(key="vision_tts_notify").set(1 if config_state.get("vision_tts_notify") else 0)


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


async def call_ollama_model_stream(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int = None,
    timeout_s: float = 30.0,
):
    """
    Stream tokens from an Ollama model.

    Yields partial response chunks as they are produced.
    """
    payload = {"model": model, "prompt": prompt, "stream": True}
    if max_tokens:
        payload["options"] = {"num_predict": max_tokens}

    timeout = httpx.Timeout(connect=3.0, read=timeout_s, write=10.0, pool=3.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", f"{base_url}/api/generate", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chunk = data.get("response") or ""
                if chunk:
                    yield chunk
                if data.get("done"):
                    final = data.get("final_response")
                    if isinstance(final, str) and final:
                        yield final
                    break


async def stream_to_realtime(
    session_id: str,
    queue: "asyncio.Queue[tuple[str, Optional[str]]]",
    ready_future: asyncio.Future,
    voice: Optional[str] = None,
) -> None:
    """Forward text/audio events to realtime TTS websocket."""
    try:
        ready_payload: Dict[str, Any] = {
            "sample_rate": REALTIME_SAMPLE_RATE_DEFAULT,
            "voice": voice,
        }
        async with websockets.connect(
            PIPELINE_REALTIME_URL,
            open_timeout=REALTIME_CONNECT_TIMEOUT,
            close_timeout=REALTIME_READ_TIMEOUT,
            ping_interval=None,
        ) as ws:
            init_payload = {"session_id": session_id, "role": "producer"}
            if voice:
                init_payload["voice"] = voice
            await ws.send(json.dumps(init_payload))
            try:
                ready_raw = await asyncio.wait_for(ws.recv(), timeout=REALTIME_READ_TIMEOUT)
                try:
                    ready_msg = json.loads(ready_raw)
                except json.JSONDecodeError:
                    ready_msg = None
            except (asyncio.TimeoutError, ConnectionClosedOK, ConnectionClosedError):
                ready_msg = None

            if isinstance(ready_msg, dict):
                sample_rate_val = ready_msg.get("sample_rate")
                try:
                    ready_payload["sample_rate"] = max(8000, int(sample_rate_val))
                except (TypeError, ValueError):
                    pass
                ready_voice = ready_msg.get("voice")
                if isinstance(ready_voice, str) and ready_voice:
                    ready_payload["voice"] = ready_voice

            if not ready_future.done():
                ready_future.set_result(dict(ready_payload))

            while True:
                kind, value = await queue.get()
                if kind == "text":
                    await ws.send(json.dumps({"type": "text", "delta": value or ""}))
                elif kind == "flush":
                    await ws.send(json.dumps({"type": "flush"}))
                elif kind == "close":
                    await ws.send(json.dumps({"type": "done"}))
                    break
        if not ready_future.done():
            ready_future.set_result(dict(ready_payload))
    except Exception as exc:
        logger.warning("Realtime streaming unavailable for session %s: %s", session_id, exc)
        if not ready_future.done():
            ready_future.set_result(False)
    finally:
        while not queue.empty():
            try:
                queue.get_nowait()
            except Exception:
                break
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


def _normalize_for_hash(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_for_hash(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_for_hash(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _stable_event_id(stage: str, turn_id: str, event: Dict[str, Any]) -> str:
    normalized = _normalize_for_hash(event)
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    material = f"{stage}:{turn_id}:{payload}"
    return hashlib.sha1(material.encode("utf-8", "ignore")).hexdigest()


def _extract_vl_summary(vl_payload: Any) -> str:
    if not isinstance(vl_payload, dict):
        return ""
    summary = vl_payload.get("summary") or vl_payload.get("text")
    if not summary:
        bullets = vl_payload.get("bullets")
        if isinstance(bullets, list) and bullets:
            candidate = bullets[0]
            if isinstance(candidate, str):
                summary = candidate
    if isinstance(summary, str):
        return summary.strip()
    return ""


def _build_vision_notification(summary: str, source: str, tags: List[str]) -> str:
    if not summary:
        return ""
    summary_clean = summary.strip()
    if not summary_clean:
        return ""

    lower_tags = [str(tag).lower() for tag in tags if isinstance(tag, str)]
    if any("slide" in tag for tag in lower_tags):
        # Heuristic tweak for common slide detections
        if summary_clean.lower().startswith(("a ", "the ", "slide", "this ")):
            text = f"I detected {summary_clean}"
        else:
            text = f"I detected a slide about {summary_clean}"
    elif source == "screen":
        text = f"I detected something on screen: {summary_clean}"
    else:
        text = f"I detected {summary_clean}"
    if text[-1] not in ".!?":
        text += "."
    return text


def _record_vision_event(stage: str, event_id: str) -> bool:
    """Return False if we have already processed this stage/event_id pair."""
    history = VISION_EVENT_HISTORY[stage]
    seen = VISION_EVENT_SEEN[stage]
    if event_id in seen:
        return False
    seen.add(event_id)
    history.append(event_id)
    if len(history) > VISION_EVENT_HISTORY_MAX:
        oldest = history.popleft()
        seen.discard(oldest)
    return True


async def _vision_tts_notify(summary: str) -> None:
    """Async placeholder for future TTS notifications."""
    logger.info("Vision TTS notify: %s", summary)


async def route_and_generate(
    conv_id: str,
    prompt: str,
    user_text: str,
    stream_handler: Optional[Callable[[str], Awaitable[None]]] = None,
) -> str:
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

    async def _generate_with_model(
        base_url: str,
        model: str,
        max_tokens: int,
        timeout_s: float,
    ) -> str:
        if stream_handler is None:
            return await call_ollama_model(base_url, model, prompt, max_tokens, timeout_s)

        result = ""
        try:
            async for chunk in call_ollama_model_stream(base_url, model, prompt, max_tokens, timeout_s):
                if not chunk:
                    continue
                result += chunk
                try:
                    await stream_handler(chunk)
                except Exception as exc:
                    logger.debug("Stream handler failed: %s", exc)
        except Exception:
            raise
        return result

    # 1) Fast path for simple queries -> Hermes3
    if not is_deep(user_text):
        try:
            ROUTE_FAST_HITS.inc()
            return await _generate_with_model(OLLAMA_TEXT_URL, TEXT_MODEL_FAST, max_tokens=384, timeout_s=20.0)
        except Exception as e:
            logger.warning(f"Hermes3 failed, fallback to 4B: {e}")
            # Fallthrough to 4B

    # 2) Sticky VL: if recently used VL successfully, try it again if idle
    if VL_TEXT_ENABLED and conv_sticky_until.get(conv_id, 0) > now and vl_idle():
        try:
            vl_queue.append(now)
            ROUTE_VL_HITS.labels(source="text").inc()
            result = await _generate_with_model(
                OLLAMA_VL_URL,
                VL_MODEL,
                max_tokens=VL_TEXT_TOKEN_LIMIT,
                timeout_s=30.0,
            )
            vl_queue.pop()
            conv_sticky_until[conv_id] = now + VL_STICKY_WINDOW_S
            return result
        except Exception as e:
            logger.warning(f"VL sticky failed: {e}")
            ROUTE_VL_FALLBACKS.labels(source="text").inc()
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
            ROUTE_VL_HITS.labels(source="text").inc()
            result = await _generate_with_model(
                OLLAMA_VL_URL,
                VL_MODEL,
                max_tokens=VL_TEXT_TOKEN_LIMIT,
                timeout_s=30.0,
            )
            conv_sticky_until[conv_id] = now + VL_STICKY_WINDOW_S
            vl_queue.pop()
            return result
        except Exception as e:
            logger.warning(f"VL opportunistic failed: {e}")
            ROUTE_VL_FALLBACKS.labels(source="text").inc()
            if vl_queue:
                vl_queue.pop()

    # 4) Deterministic fallback to Qwen3-4B
    try:
        ROUTE_4B_HITS.inc()
        return await _generate_with_model(
            OLLAMA_TEXT_URL,
            TEXT_MODEL,
            max_tokens=640,
            timeout_s=25.0,
        )
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

    # --- VISION CONTEXT INJECTION ---
    vision_ctx = await _fetch_vision_context(user_text)
    vision_section = ""
    vision_injected = False
    if vision_ctx:
        vision_section = f"""

### Visual Context (recent screen/camera analysis)
{vision_ctx}
---
"""
        vision_injected = True
        logger.info(f"Vision context injected: {len(vision_ctx)} chars")

    # --- PROMPT CONSTRUCTION ---
    sys = payload.get("system_prompt", "You are GLaDOS. Be concise with dry wit.")
    prompt = f"""{sys}

### Retrieved memory (may be relevant; ignore if off-topic)
{ctx or "- none -"}
---
{vision_section}
Safety: Use retrieved memory only if relevant; never repeat placeholders like [email] or [phone].

User: {user_text}
Assistant:"""

    # --- LLM CALL (with intelligent routing) ---
    realtime_queue: Optional[asyncio.Queue] = None
    realtime_task: Optional[asyncio.Task] = None
    stream_ready: Optional[asyncio.Future] = None
    realtime_ready_info: Optional[Dict[str, Any]] = None
    flush_markers = tuple(REALTIME_FLUSH_MARKERS)

    async def _stream_chunk(chunk: str) -> None:
        if not chunk or realtime_queue is None:
            return
        await realtime_queue.put(("text", chunk))
        if any(marker in chunk for marker in flush_markers):
            await realtime_queue.put(("flush", None))

    if REALTIME_STREAM_ENABLED:
        try:
            loop = asyncio.get_running_loop()
            realtime_queue = asyncio.Queue()
            stream_ready = loop.create_future()
            realtime_task = asyncio.create_task(
                stream_to_realtime(
                    turn_id,
                    realtime_queue,
                    stream_ready,
                    None,
                )
            )
            ready = await asyncio.wait_for(stream_ready, REALTIME_CONNECT_TIMEOUT + 1.0)
            if not isinstance(ready, dict):
                realtime_queue = None
            else:
                realtime_ready_info = ready
        except Exception as exc:
            logger.debug("Realtime stream setup failed: %s", exc)
            realtime_queue = None
        finally:
            if realtime_queue is None and realtime_task:
                realtime_task.cancel()
                with suppress(Exception):
                    await realtime_task
                realtime_task = None

    try:
        if realtime_queue is not None:
            reply = await route_and_generate(conv_id, prompt, user_text, stream_handler=_stream_chunk)
        else:
            reply = await route_and_generate(conv_id, prompt, user_text)
    finally:
        if realtime_queue is not None:
            try:
                await realtime_queue.put(("flush", None))
                await realtime_queue.put(("close", None))
            except Exception:
                pass
            if realtime_task:
                with suppress(Exception):
                    await realtime_task

    logger.info(f"LLM reply: {reply[:100]}...")
    if REALTIME_STREAM_ENABLED and realtime_queue is not None:
        sample_rate_hint: Optional[int] = None
        voice_hint: Optional[str] = None
        if isinstance(realtime_ready_info, dict):
            sample_rate_hint = realtime_ready_info.get("sample_rate")
            raw_voice = realtime_ready_info.get("voice")
            if isinstance(raw_voice, str) and raw_voice:
                voice_hint = raw_voice
        await _register_realtime_session(reply, turn_id, voice_hint, sample_rate_hint)

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
        "ctx_chars": len(ctx),
        "vision_injected": vision_injected
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


@app.post("/realtime/claim")
async def realtime_claim(payload: Dict = Body(...)) -> JSONResponse:
    """Allow consumers to claim realtime session info for a reply."""
    if not REALTIME_STREAM_ENABLED:
        raise HTTPException(status_code=404, detail="Realtime streaming disabled")
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail="text required")
    entry = await _claim_realtime_session(text)
    if entry is None:
        raise HTTPException(status_code=404, detail="Realtime session not found")
    result = dict(entry)
    result.pop("expires", None)
    result.pop("_aliases", None)
    return JSONResponse(result)


@app.post("/realtime/claim")
async def realtime_claim(payload: Dict = Body(...)) -> JSONResponse:
    if not REALTIME_STREAM_ENABLED:
        raise HTTPException(status_code=404, detail="Realtime streaming disabled")
    text = payload.get("text")
    if not isinstance(text, str) or not text:
        raise HTTPException(status_code=400, detail="text required")
    entry = await _claim_realtime_session(text)
    if entry is None:
        raise HTTPException(status_code=404, detail="Realtime session not found")
    result = dict(entry)
    result.pop("expires", None)
    result.pop("_aliases", None)
    return JSONResponse(result)


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
