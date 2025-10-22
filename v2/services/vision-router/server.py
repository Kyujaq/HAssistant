import asyncio
import logging
import os
import json
import time
import uuid
from collections import deque
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from scoring import compute_usefulness
from common.gpu_stats import nvml_available, snapshot_gpus

ORCH = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8020")
VL_GATEWAY = os.getenv("VL_GATEWAY_URL", "http://orchestrator:8020")
ESCL_ENABLED = os.getenv("VISION_ESCALATE_VL", "1") == "1"
THRESH = float(os.getenv("VISION_ESCALATE_THRESHOLD", "0.55"))
MAX_FRAMES = int(os.getenv("VISION_MAX_FRAMES", "3"))
LOCK_ON_ESCALATE = os.getenv("VISION_LOCK_ON_ESCALATE", "1") == "1"

EVENTS_TOTAL = Counter("vision_events_total", "total vision events", ["source"])
ESC_TOTAL = Counter("vision_escalations_total", "total escalations", ["reason"])
ESC_LAT = Histogram("vision_escalation_latency_ms", "VL escalation latency (ms)")
OCR_LAT = Histogram("vision_k80_ocr_latency_ms", "K80 preproc/ocr latency (ms)")
LOCK_G = Gauge("vision_lock", "1 if lock held else 0")
QUEUE_G = Gauge("vision_pending_jobs", "pending escalations")
HEALTH_G = Gauge("vision_health", "1 if healthy")
CONFIG_G = Gauge("vision_config_state", "configuration flags", ["key"])
SKIP_TOTAL = Counter("vision_events_skipped_total", "events skipped due to configuration", ["reason"])
VL_FAILOVER_TOTAL = Counter("vision_vl_failovers_total", "VL escalation failures")
ANALYZE_TOTAL = Counter("vision_analyze_requests_total", "ad-hoc analyze requests", ["source"])
GPU_UTIL_G = Gauge("vision_gpu_util_percent", "GPU utilization percent", ["index"])
GPU_MEM_FREE_G = Gauge("vision_gpu_mem_free_gb", "GPU free memory (GB)", ["index"])

FRIGATE_EVENTS = Counter("frigate_events_seen_total", "Frigate events seen by router")
FRIGATE_SNAPS = Counter("frigate_snapshots_fetched_total", "Snapshots attached to Frigate events")

# State
pending_jobs = 0
lock_held = False
total_events = 0
total_escalations = 0
_gpu_cache: Dict[str, Any] = {"gpus": [], "last_update": 0.0}
_gpu_util_history: deque = deque(maxlen=12)  # ~60s history at 5s intervals
_threshold_adjusted_at = 0.0

config: Dict[str, Any] = {
    "vision_on": True,
    "screen_watch_on": True,
    "threshold": THRESH,
    "max_frames": MAX_FRAMES,
    "escalate_vl": ESCL_ENABLED,
}


def _update_config_metrics() -> None:
    CONFIG_G.labels("vision_on").set(1.0 if config.get("vision_on", True) else 0.0)
    CONFIG_G.labels("screen_watch_on").set(1.0 if config.get("screen_watch_on", True) else 0.0)
    CONFIG_G.labels("threshold").set(float(config.get("threshold", THRESH)))
    CONFIG_G.labels("max_frames").set(float(config.get("max_frames", MAX_FRAMES)))
    CONFIG_G.labels("escalate_vl").set(1.0 if config.get("escalate_vl", ESCL_ENABLED) else 0.0)


def _gpu_stats() -> Dict[str, Any]:
    """Return cached GPU stats or refresh if stale (>3s)."""
    now = time.time()
    if now - _gpu_cache.get("last_update", 0.0) > 3.0:
        gpus = snapshot_gpus() if nvml_available() else []
        _gpu_cache["gpus"] = gpus
        _gpu_cache["last_update"] = now
        for gpu in gpus:
            index = str(gpu.get("index", 0))
            GPU_UTIL_G.labels(index=index).set(gpu.get("util", 0.0))
            GPU_MEM_FREE_G.labels(index=index).set(gpu.get("mem_free_gb", 0.0))
    return {"gpus": _gpu_cache.get("gpus", [])}


def _check_backpressure() -> None:
    """Auto-adjust threshold if queue or GPU util is high."""
    global _threshold_adjusted_at
    now = time.time()

    # Only check every 30s
    if now - _threshold_adjusted_at < 30.0:
        return

    # Check queue depth
    if pending_jobs > 5:
        current = config.get("threshold", THRESH)
        new_threshold = min(0.85, current + 0.1)
        if new_threshold > current:
            config["threshold"] = new_threshold
            _update_config_metrics()
            logger.warning(f"Backpressure: queue_depth={pending_jobs}, raised threshold {current:.2f} → {new_threshold:.2f}")
            _threshold_adjusted_at = now
            return

    # Check GPU util history (need >85% for 60s)
    if len(_gpu_util_history) >= 12:
        avg_util = sum(_gpu_util_history) / len(_gpu_util_history)
        if avg_util > 85.0:
            current = config.get("threshold", THRESH)
            new_threshold = min(0.85, current + 0.1)
            if new_threshold > current:
                config["threshold"] = new_threshold
                _update_config_metrics()
                logger.warning(f"Backpressure: avg_gpu_util={avg_util:.1f}%, raised threshold {current:.2f} → {new_threshold:.2f}")
                _threshold_adjusted_at = now

_update_config_metrics()

app = FastAPI(title="vision-router", version="0.1.0")
logger = logging.getLogger("vision-router")
logging.basicConfig(level=logging.INFO)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "escalate": ESCL_ENABLED,
        "threshold": config.get("threshold", THRESH),
        "vision_on": config.get("vision_on", True),
    }


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/config")
def get_config() -> Dict[str, Any]:
    return config


@app.post("/config")
def set_config(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    if "vision_on" in payload:
        config["vision_on"] = bool(payload["vision_on"])
    if "screen_watch_on" in payload:
        config["screen_watch_on"] = bool(payload["screen_watch_on"])
    if "threshold" in payload:
        config["threshold"] = float(payload["threshold"])
    if "max_frames" in payload:
        config["max_frames"] = max(1, int(payload["max_frames"]))
    if "escalate_vl" in payload:
        config["escalate_vl"] = bool(payload["escalate_vl"])
    _update_config_metrics()
    logger.info("Updated config: %s", config)
    return config


@app.get("/stats")
def stats() -> Dict[str, Any]:
    return {
        "queue_depth": max(0, pending_jobs),
        "lock_enabled": bool(lock_held),
        "events_total": total_events,
        "escalations_total": total_escalations,
        "config": config,
        **_gpu_stats(),
    }


@app.post("/lock")
async def set_lock(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    global lock_held
    enabled = bool(payload.get("enabled", True))
    lock_held = enabled
    LOCK_G.set(1 if enabled else 0)
    try:
        async with httpx.AsyncClient(timeout=4.0) as session:
            await session.post(f"{ORCH}/router/vision_lock", json={"enabled": enabled})
    except Exception:
        pass
    return {"enabled": lock_held}


@app.get("/lock")
def get_lock() -> Dict[str, Any]:
    return {"enabled": bool(lock_held)}


async def _post_orchestrator(event: Dict[str, Any]) -> None:
    try:
        async with httpx.AsyncClient(timeout=8.0) as session:
            await session.post(f"{ORCH}/vision/event", json=event)
    except Exception as exc:
        logger.warning("orchestrator push failed: %s", exc)


async def _escalate_to_vl(bundle: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=60.0) as session:
            response = await session.post(f"{VL_GATEWAY}/vision/vl_summarize", json=bundle)
            response.raise_for_status()
            ESC_LAT.observe((time.time() - start) * 1000)
            return response.json()
    except Exception as exc:
        ESC_LAT.observe((time.time() - start) * 1000)
        VL_FAILOVER_TOTAL.inc()
        logger.warning("VL escalate failed: %s", exc)
        return {"error": str(exc)}


def _build_vl_bundle(event: Dict[str, Any], top_k: int) -> Dict[str, Any]:
    frames: List[Dict[str, Any]] = event.get("frames") or []
    ranked = sorted(
        frames,
        key=lambda frame: len(((frame.get("ocr") or {}).get("text") or "")),
        reverse=True,
    )
    top_frames = ranked[: max(1, top_k)]
    return {
        "source": event.get("source"),
        "frames": [{"url": frame.get("url"), "ocr": (frame.get("ocr") or {})} for frame in top_frames],
        "hints": {
            "ocr_text": "\n\n".join((frame.get("ocr") or {}).get("text") or "" for frame in top_frames)[:4000],
            "tags": event.get("tags") or [],
            "detections": event.get("detections") or [],
        },
        "task": "meeting" if "meeting" in (event.get("tags") or []) else "generic",
        "ts": event.get("ts"),
        "meta": event.get("meta") or {},
    }


@app.post("/events")
async def ingest_event(
    payload: Optional[Dict[str, Any]] = Body(default=None),
    json_payload: Optional[str] = Form(default=None),
    snapshot: Optional[UploadFile] = File(default=None),
) -> JSONResponse:
    global pending_jobs, lock_held, total_events, total_escalations

    if json_payload is not None:
        try:
            event: Dict[str, Any] = json.loads(json_payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid form JSON: {exc}") from exc
    else:
        event = payload or {}

    if not isinstance(event, dict) or not event:
        raise HTTPException(status_code=400, detail="Event payload required")

    source = event.get("source", "unknown")

    if source == "frigate":
        FRIGATE_EVENTS.inc()

    snapshot_size = 0
    if snapshot is not None:
        FRIGATE_SNAPS.inc()
        data = await snapshot.read()
        snapshot_size = len(data)
        meta = event.setdefault("meta", {})
        meta.update(
            {
                "snapshot_size": snapshot_size,
                "snapshot_filename": getattr(snapshot, "filename", None),
                "snapshot_content_type": snapshot.content_type,
            }
        )
    else:
        event.setdefault("meta", {})

    if not config.get("vision_on", True):
        EVENTS_TOTAL.labels(source).inc()
        SKIP_TOTAL.labels(reason="vision_off").inc()
        total_events += 1
        return JSONResponse({"id": str(uuid.uuid4()), "skipped": True, "reason": "vision_off"})

    EVENTS_TOTAL.labels(source).inc()
    total_events += 1

    score = compute_usefulness(event)
    threshold = float(config.get("threshold", THRESH))
    should_escalate = config.get("escalate_vl", ESCL_ENABLED) and score >= threshold

    if not config.get("screen_watch_on", True) and source.lower() == "screen":
        if should_escalate:
            SKIP_TOTAL.labels(reason="screen_disabled").inc()
        should_escalate = False

    event_id = str(uuid.uuid4())
    unified = {
        "id": event_id,
        "source": source,
        "ts": event.get("ts"),
        "score": round(score, 3),
        "escalated": should_escalate,
        "k80": {
            "frames": event.get("frames") or [],
            "detections": event.get("detections") or [],
            "tags": event.get("tags") or [],
            "meta": event.get("meta") or {},
        },
        "vl": None,
    }

    asyncio.create_task(_post_orchestrator(unified))

    if should_escalate:
        _check_backpressure()
        if LOCK_ON_ESCALATE and not lock_held:
            await set_lock({"enabled": True})
        pending_jobs += 1
        QUEUE_G.set(pending_jobs)
        ESC_TOTAL.labels(reason="useful").inc()
        top_k = int(config.get("max_frames", MAX_FRAMES))
        bundle = _build_vl_bundle(event, top_k)
        result = await _escalate_to_vl(bundle)
        total_escalations += 1
        pending_jobs = max(0, pending_jobs - 1)
        QUEUE_G.set(pending_jobs)
        if LOCK_ON_ESCALATE and lock_held:
            await set_lock({"enabled": False})

        unified["vl"] = result
        asyncio.create_task(_post_orchestrator(unified))

    return JSONResponse({"id": event_id, "score": score, "escalated": bool(unified["vl"])})


@app.post("/analyze")
async def analyze_adhoc(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Ad-hoc analysis for HA calls with explicit frames/urls.
    Bypasses vision_on/screen_watch_on checks and always escalates to VL if escalate_vl is enabled.
    """
    global pending_jobs, lock_held
    source = payload.get("source", "adhoc")
    ANALYZE_TOTAL.labels(source).inc()

    # Build VL bundle from explicit frames
    top_k = int(config.get("max_frames", MAX_FRAMES))
    bundle = _build_vl_bundle(payload, top_k)

    event_id = str(uuid.uuid4())
    result: Dict[str, Any] = {"id": event_id, "source": source}

    if not config.get("escalate_vl", ESCL_ENABLED):
        SKIP_TOTAL.labels(reason="vl_disabled").inc()
        result["escalated"] = False
        result["reason"] = "escalate_vl disabled"
        return JSONResponse(result)

    # Escalate to VL
    _check_backpressure()
    if LOCK_ON_ESCALATE and not lock_held:
        await set_lock({"enabled": True})

    pending_jobs += 1
    QUEUE_G.set(pending_jobs)
    ESC_TOTAL.labels(reason="adhoc").inc()

    vl_result = await _escalate_to_vl(bundle)

    pending_jobs = max(0, pending_jobs - 1)
    QUEUE_G.set(pending_jobs)
    if LOCK_ON_ESCALATE and lock_held:
        await set_lock({"enabled": False})

    result["escalated"] = True
    result["vl"] = vl_result
    result["bundle"] = bundle  # Include bundle for debugging

    return JSONResponse(result)


async def _gpu_poller_task() -> None:
    """Background task to poll GPU stats every 5s and maintain utilization history."""
    while True:
        await asyncio.sleep(5.0)
        try:
            gpus = snapshot_gpus() if nvml_available() else []
            if gpus:
                # Calculate average utilization across all GPUs
                avg_util = sum(gpu.get("util", 0.0) for gpu in gpus) / len(gpus)
                _gpu_util_history.append(avg_util)
                # Update cache
                _gpu_cache["gpus"] = gpus
                _gpu_cache["last_update"] = time.time()
                # Update Prometheus gauges
                for gpu in gpus:
                    index = str(gpu.get("index", 0))
                    GPU_UTIL_G.labels(index=index).set(gpu.get("util", 0.0))
                    GPU_MEM_FREE_G.labels(index=index).set(gpu.get("mem_free_gb", 0.0))
        except Exception as exc:
            logger.warning(f"GPU poller error: {exc}")


@app.on_event("startup")
async def on_start() -> None:
    HEALTH_G.set(1.0)
    _update_config_metrics()
    # Start background GPU poller
    asyncio.create_task(_gpu_poller_task())
    logger.info("vision-router started, GPU poller running")


@app.on_event("shutdown")
async def on_stop() -> None:
    HEALTH_G.set(0.0)
