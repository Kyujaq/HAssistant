import asyncio
import base64
import io
import json
import os
import time
import uuid
from collections import deque
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from PIL import Image
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from common.event_schema import build_event
from common.gpu_stats import nvml_available, snapshot_gpus

APP_TITLE = "vision-gateway"
VERSION = "0.1.0"
ORCH_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8020")
ROUTER_URL = os.getenv("VISION_ROUTER_URL", "http://vision-router:8050")
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8051")

registry = CollectorRegistry()
EVENTS_TOTAL = Counter("vision_gateway_events_total", "Frames processed", ["kind"], registry=registry)
EVENT_LAT_MS = Histogram("vision_gateway_processing_ms", "Processing latency (ms)", ["stage"], registry=registry)
MJPEG_CLIENTS = Gauge("vision_gateway_mjpeg_clients", "Active MJPEG clients", registry=registry)
GPU_UTIL = Gauge("vision_gateway_gpu_util_percent", "GPU utilisation percent", ["index"], registry=registry)
GPU_MEM_FREE = Gauge("vision_gateway_gpu_mem_free_gb", "GPU free memory (GB)", ["index"], registry=registry)

app = FastAPI(title=APP_TITLE, version=VERSION)

latest_frame_bytes: Optional[bytes] = None
latest_frame_lock = asyncio.Lock()
FRAME_TTL_SECONDS = 300
_frame_store: Dict[str, Dict[str, Any]] = {}


class RateTracker:
    def __init__(self, window_seconds: float = 60.0) -> None:
        self.window = window_seconds
        self._events: deque[float] = deque()

    def mark(self) -> None:
        now = time.time()
        self._events.append(now)
        self._trim(now)

    def rate(self) -> float:
        now = time.time()
        self._trim(now)
        if not self._events:
            return 0.0
        return len(self._events) / self.window

    def _trim(self, now: float) -> None:
        cutoff = now - self.window
        while self._events and self._events[0] < cutoff:
            self._events.popleft()


rate_tracker = RateTracker()
last_event_ts: Optional[float] = None
sent_events = 0


def _gpu_stats() -> List[Dict[str, Any]]:
    gpus = snapshot_gpus() if nvml_available() else []
    for gpu in gpus:
        index = str(gpu.get("index", 0))
        GPU_UTIL.labels(index=index).set(gpu.get("util", 0.0))
        GPU_MEM_FREE.labels(index=index).set(gpu.get("mem_free_gb", 0.0))
    return gpus


async def _persist_frame(frame_id: str, data: bytes, content_type: str = "image/jpeg") -> None:
    _frame_store[frame_id] = {
        "bytes": data,
        "content_type": content_type,
        "ts": time.time(),
    }


async def _cleanup_frames() -> None:
    while True:
        await asyncio.sleep(60)
        cutoff = time.time() - FRAME_TTL_SECONDS
        stale = [key for key, meta in _frame_store.items() if meta["ts"] < cutoff]
        for key in stale:
            _frame_store.pop(key, None)


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(_cleanup_frames())
    _gpu_stats()


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True, "router": ROUTER_URL, "orch": ORCH_URL}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(registry), media_type="text/plain; version=0.0.4")


@app.get("/stats")
async def stats() -> Dict[str, Any]:
    return {
        "fps": rate_tracker.rate(),
        "last_event_ts": last_event_ts,
        "events_sent": sent_events,
        "router": ROUTER_URL,
        "gpu": _gpu_stats(),
        "frame_store": len(_frame_store),
    }


async def _download_image(url: str) -> bytes:
    timeout = httpx.Timeout(15.0, read=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _heuristic_tags(np_img: np.ndarray) -> List[str]:
    tags: List[str] = []
    mean = float(np.mean(np_img))
    std = float(np.std(np_img))
    if mean > 200:
        tags.append("bright")
    if std < 40:
        tags.append("low_contrast")
    if mean < 50:
        tags.append("dark")
    if np_img.shape[1] > np_img.shape[0]:
        tags.append("landscape")
    return tags


async def _post_event(event: Dict[str, Any]) -> Dict[str, Any]:
    timeout = httpx.Timeout(10.0, read=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{ROUTER_URL}/events", json=event)
        response.raise_for_status()
        return response.json()


@app.post("/frame")
async def ingest_frame(
    file: Optional[UploadFile] = File(default=None),
    image_url: Optional[str] = Form(default=None),
    image_b64: Optional[str] = Form(default=None),
    source: str = Form(default="screen.local"),
    ts: Optional[float] = Form(default=None),
    tags: Optional[str] = Form(default=None),
    meta: Optional[str] = Form(default=None),
    ocr_text: Optional[str] = Form(default=None),
    ocr_conf: Optional[float] = Form(default=None),
) -> JSONResponse:
    start = time.time()
    if file is not None:
        data = await file.read()
    elif image_b64:
        data = base64.b64decode(image_b64)
    elif image_url:
        data = await _download_image(image_url)
    else:
        raise HTTPException(status_code=400, detail="Provide file upload, image_url, or image_b64")

    img = Image.open(io.BytesIO(data)).convert("RGB")
    np_img = np.asarray(img)
    derived_tags = _heuristic_tags(np_img)

    frame_id = uuid.uuid4().hex
    await _persist_frame(frame_id, data)

    frame_url = f"{PUBLIC_URL.rstrip('/')}/frames/{frame_id}.jpg"
    frame_obj: Dict[str, Any] = {
        "url": frame_url,
        "width": img.width,
        "height": img.height,
        "ocr": {},
    }
    if ocr_text:
        frame_obj["ocr"]["text"] = ocr_text
    if ocr_conf is not None:
        frame_obj["ocr"]["conf"] = float(ocr_conf)

    combined_tags: List[str] = []
    if tags:
        combined_tags.extend(tag.strip() for tag in tags.split(",") if tag.strip())
    combined_tags.extend(derived_tags)

    meta_dict: Dict[str, Any] = {}
    if meta:
        try:
            meta_dict = json.loads(meta)
        except Exception as exc:  # pragma: no cover - passthrough
            raise HTTPException(status_code=400, detail=f"Invalid meta JSON: {exc}")

    event: Dict[str, Any] = {
        "source": source,
        "ts": ts or time.time(),
        "frames": [frame_obj],
        "detections": [],
        "tags": combined_tags,
        "meta": meta_dict,
    }

    build_event(event)  # schema validation

    global latest_frame_bytes, last_event_ts, sent_events
    async with latest_frame_lock:
        latest_frame_bytes = data

    EVENTS_TOTAL.labels(kind="screen").inc()
    rate_tracker.mark()
    last_event_ts = time.time()

    response_payload = await _post_event(event)
    sent_events += 1

    elapsed_ms = (time.time() - start) * 1000
    EVENT_LAT_MS.labels(stage="total").observe(elapsed_ms)

    return JSONResponse({"event_id": event["frames"][0]["url"], "router": response_payload})


@app.get("/frames/{frame_id}.jpg")
async def get_frame(frame_id: str):
    frame = _frame_store.get(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame expired")
    return StreamingResponse(io.BytesIO(frame["bytes"]), media_type=frame.get("content_type", "image/jpeg"))


@app.get("/frames/latest.jpg")
async def latest_frame():
    async with latest_frame_lock:
        frame = latest_frame_bytes
    if frame is None:
        raise HTTPException(status_code=404, detail="No frame available")
    return StreamingResponse(io.BytesIO(frame), media_type="image/jpeg")


@app.get("/mjpeg/screen")
async def mjpeg_screen():
    boundary = "frame"

    async def _gen():
        MJPEG_CLIENTS.inc()
        try:
            while True:
                async with latest_frame_lock:
                    frame = latest_frame_bytes
                if frame is None:
                    await asyncio.sleep(0.1)
                    continue
                yield (
                    b"--" + boundary.encode() + b"\r\n"
                    + b"Content-Type: image/jpeg\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
                await asyncio.sleep(0.2)
        finally:
            MJPEG_CLIENTS.dec()

    return StreamingResponse(_gen(), media_type=f"multipart/x-mixed-replace; boundary={boundary}")
