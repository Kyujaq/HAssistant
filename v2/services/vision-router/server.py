import asyncio
import logging
import os
import time
import uuid
from typing import Any, Dict, List

import httpx
from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from scoring import compute_usefulness

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

pending_jobs = 0
lock_held = False

app = FastAPI(title="vision-router", version="0.1.0")
logger = logging.getLogger("vision-router")
logging.basicConfig(level=logging.INFO)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "escalate": ESCL_ENABLED, "threshold": THRESH}


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
        logger.warning("VL escalate failed: %s", exc)
        return {"error": str(exc)}


def _build_vl_bundle(event: Dict[str, Any]) -> Dict[str, Any]:
    frames: List[Dict[str, Any]] = event.get("frames") or []
    ranked = sorted(
        frames,
        key=lambda frame: len(((frame.get("ocr") or {}).get("text") or "")),
        reverse=True,
    )
    top_frames = ranked[:MAX_FRAMES]
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
async def ingest_event(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    global pending_jobs, lock_held
    source = payload.get("source", "unknown")
    EVENTS_TOTAL.labels(source).inc()

    score = compute_usefulness(payload)
    should_escalate = ESCL_ENABLED and score >= THRESH

    event_id = str(uuid.uuid4())
    unified = {
        "id": event_id,
        "source": source,
        "ts": payload.get("ts"),
        "score": round(score, 3),
        "escalated": should_escalate,
        "k80": {
            "frames": payload.get("frames") or [],
            "detections": payload.get("detections") or [],
            "tags": payload.get("tags") or [],
            "meta": payload.get("meta") or {},
        },
        "vl": None,
    }

    asyncio.create_task(_post_orchestrator(unified))

    if should_escalate:
        if LOCK_ON_ESCALATE and not lock_held:
            await set_lock({"enabled": True})
        pending_jobs += 1
        QUEUE_G.set(pending_jobs)
        ESC_TOTAL.labels(reason="useful").inc()
        bundle = _build_vl_bundle(payload)
        result = await _escalate_to_vl(bundle)
        pending_jobs = max(0, pending_jobs - 1)
        QUEUE_G.set(pending_jobs)
        if LOCK_ON_ESCALATE and lock_held:
            await set_lock({"enabled": False})

        unified["vl"] = result
        asyncio.create_task(_post_orchestrator(unified))

    return JSONResponse({"id": event_id, "score": score, "escalated": bool(unified["vl"])})


@app.on_event("startup")
async def on_start() -> None:
    HEALTH_G.set(1.0)


@app.on_event("shutdown")
async def on_stop() -> None:
    HEALTH_G.set(0.0)
