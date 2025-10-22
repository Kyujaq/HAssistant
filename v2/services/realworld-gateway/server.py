import asyncio
import base64
import io
import json
import logging
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
from event_worker import fetch_snapshot, post_event_to_router
from frigate_mqtt import FrigateSubscriber

APP_TITLE = "realworld-gateway"
VERSION = "0.1.0"
ORCH_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8020")
ROUTER_URL = os.getenv("VISION_ROUTER_URL", "http://vision-router:8050")
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8052")

FRIGATE_MQTT_HOST = os.getenv("FRIGATE_MQTT_HOST", "127.0.0.1")
FRIGATE_MQTT_TOPIC = os.getenv("FRIGATE_MQTT_TOPIC", "frigate/events")
FRIGATE_EVENT_QUEUE_MAX = int(os.getenv("FRIGATE_EVENT_QUEUE_MAX", "100"))

registry = CollectorRegistry()
logger = logging.getLogger(APP_TITLE)
logging.basicConfig(level=logging.INFO)
EVENTS_TOTAL = Counter("realworld_gateway_events_total", "Frames processed", ["kind"], registry=registry)
PROCESS_MS = Histogram("realworld_gateway_processing_ms", "Processing latency (ms)", ["stage"], registry=registry)
MJPEG_CLIENTS = Gauge("realworld_gateway_mjpeg_clients", "Active MJPEG clients", registry=registry)
GPU_UTIL = Gauge("realworld_gateway_gpu_util_percent", "GPU utilisation percent", ["index"], registry=registry)
GPU_MEM_FREE = Gauge("realworld_gateway_gpu_mem_free_gb", "GPU free memory (GB)", ["index"], registry=registry)

app = FastAPI(title=APP_TITLE, version=VERSION)

latest_frame_bytes: Optional[bytes] = None
latest_frame_lock = asyncio.Lock()
FRAME_TTL_SECONDS = 300
_frame_store: Dict[str, Dict[str, Any]] = {}
_event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=FRIGATE_EVENT_QUEUE_MAX)
_mqtt_subscriber: Optional[FrigateSubscriber] = None


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


def _on_frigate_event(payload: Dict[str, Any]) -> None:
    """Callback bridge from MQTT into the async event queue."""
    if not isinstance(payload, dict):
        return
    event_type = payload.get("type")
    if event_type not in {"new", "end"}:
        return
    event_data = payload.get("after")
    if not isinstance(event_data, dict):
        return
    if event_type == "new":
        return
    try:
        _event_queue.put_nowait(event_data)
    except asyncio.QueueFull:
        logger.warning("Frigate event queue full; dropping %s", event_data.get("id"))

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

async def _event_consumer_loop() -> None:
    global latest_frame_bytes, last_event_ts, sent_events
    while True:
        event = await _event_queue.get()
        start = time.time()
        try:
            event_id = event.get("id")
            snapshot = await fetch_snapshot(event_id)
            tags: List[str] = []
            detections: List[Dict[str, Any]] = []
            frame_url: Optional[str] = None
            frame_width: Optional[int] = None
            frame_height: Optional[int] = None
            if snapshot:
                try:
                    img = Image.open(io.BytesIO(snapshot)).convert("RGB")
                    np_img = np.asarray(img)
                    heuristics = _motion_heuristics(np_img)
                    tags.extend(heuristics.get("tags", []))
                    detections.extend(heuristics.get("detections", []))
                    frame_id = uuid.uuid4().hex
                    await _persist_frame(frame_id, snapshot)
                    frame_url = f"{PUBLIC_URL.rstrip('/')}/frames/{frame_id}.jpg"
                    frame_width, frame_height = img.width, img.height
                    async with latest_frame_lock:
                        latest_frame_bytes = snapshot
                except Exception as exc:
                    logger.warning("Snapshot analysis failed for %s: %s", event_id, exc)

            frames: List[Dict[str, Any]] = []
            if frame_url:
                frames.append(
                    {
                        "url": frame_url,
                        "width": frame_width,
                        "height": frame_height,
                        "ocr": {},
                    }
                )

            payload: Dict[str, Any] = {
                "source": "frigate",
                "event_id": event_id,
                "camera": event.get("camera"),
                "label": event.get("label"),
                "score": event.get("score"),
                "start_time": event.get("start_time"),
                "end_time": event.get("end_time"),
                "zones": event.get("entered_zones", []),
                "tags": tags,
                "detections": detections,
                "frames": frames,
                "ts": event.get("end_time") or event.get("start_time") or time.time(),
                "meta": {
                    "frigate": event,
                    "snapshot_available": bool(snapshot),
                    "frame_url": frame_url,
                },
            }

            EVENTS_TOTAL.labels(kind="frigate").inc()
            rate_tracker.mark()
            last_event_ts = time.time()

            await post_event_to_router(payload, snapshot)
            sent_events += 1
            PROCESS_MS.labels(stage="frigate").observe((time.time() - start) * 1000)
        except Exception as exc:
            logger.exception("Event processing failed: %s", exc)
        finally:
            _event_queue.task_done()

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
    global _mqtt_subscriber
    asyncio.create_task(_cleanup_frames())
    asyncio.create_task(_event_consumer_loop())
    _gpu_stats()
    try:
        _mqtt_subscriber = FrigateSubscriber(
            broker=FRIGATE_MQTT_HOST,
            topic=FRIGATE_MQTT_TOPIC,
            on_event=_on_frigate_event,
        )
        _mqtt_subscriber.start()
        logger.info("Subscribed to Frigate MQTT broker=%s topic=%s", FRIGATE_MQTT_HOST, FRIGATE_MQTT_TOPIC)
    except Exception as exc:
        logger.exception("Unable to start Frigate subscriber: %s", exc)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if _mqtt_subscriber:
        try:
            _mqtt_subscriber.stop()
        except Exception:
            pass


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
        "event_queue": _event_queue.qsize(),
        "mqtt_topic": FRIGATE_MQTT_TOPIC,
    }


async def _download_image(url: str) -> bytes:
    timeout = httpx.Timeout(15.0, read=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _motion_heuristics(np_img: np.ndarray) -> Dict[str, Any]:
    gray = np_img.mean(axis=2)
    dy = np.abs(np.diff(gray, axis=0)).mean()
    dx = np.abs(np.diff(gray, axis=1)).mean()
    motion_score = float((dx + dy) / 2.0)
    detections: List[Dict[str, Any]] = []
    tags: List[str] = []
    if motion_score > 12.0:
        detections.append({"label": "motion", "conf": min(1.0, motion_score / 50.0)})
        tags.append("motion")
    brightness = float(gray.mean())
    if brightness > 160:
        tags.append("well_lit")
    return {"detections": detections, "tags": tags}


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
    source: str = Form(default="camera.front"),
    ts: Optional[float] = Form(default=None),
    tags: Optional[str] = Form(default=None),
    detections: Optional[str] = Form(default=None),
    meta: Optional[str] = Form(default=None),
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
    heuristics = _motion_heuristics(np_img)

    frame_id = uuid.uuid4().hex
    await _persist_frame(frame_id, data)
    frame_url = f"{PUBLIC_URL.rstrip('/')}/frames/{frame_id}.jpg"

    combined_tags: List[str] = []
    if tags:
        combined_tags.extend(tag.strip() for tag in tags.split(",") if tag.strip())
    combined_tags.extend(heuristics["tags"])

    parsed_detections: List[Dict[str, Any]] = heuristics["detections"]
    if detections:
        try:
            extra = json.loads(detections)
            if isinstance(extra, list):
                parsed_detections.extend(extra)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid detections JSON: {exc}")

    meta_dict: Dict[str, Any] = {}
    if meta:
        try:
            meta_dict = json.loads(meta)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid meta JSON: {exc}")

    event: Dict[str, Any] = {
        "source": source,
        "ts": ts or time.time(),
        "frames": [
            {
                "url": frame_url,
                "width": img.width,
                "height": img.height,
                "ocr": {},
            }
        ],
        "detections": parsed_detections,
        "tags": combined_tags,
        "meta": meta_dict,
    }

    build_event(event)

    global latest_frame_bytes, last_event_ts, sent_events
    async with latest_frame_lock:
        latest_frame_bytes = data

    EVENTS_TOTAL.labels(kind="camera").inc()
    rate_tracker.mark()
    last_event_ts = time.time()

    response_payload = await _post_event(event)
    sent_events += 1

    elapsed_ms = (time.time() - start) * 1000
    PROCESS_MS.labels(stage="total").observe(elapsed_ms)

    return JSONResponse({"frame": frame_url, "router": response_payload})


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


@app.get("/mjpeg/cam")
async def mjpeg_cam():
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
