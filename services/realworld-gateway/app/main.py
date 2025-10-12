import os, time, threading, base64, asyncio
from typing import List, Dict, Any
from datetime import datetime

import numpy as np
import cv2
import requests
from fastapi import FastAPI, Response
from pydantic import BaseModel

# ---------------------- CPU friendliness ----------------------
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
try:
    cv2.setNumThreads(1)
except Exception:
    pass

# ---------------------- Config (env) ----------------------
HA_BASE = os.getenv("HA_BASE_URL", "")
HA_TOKEN = os.getenv("HA_TOKEN", "")

OLLAMA_VISION_BASE  = os.getenv("OLLAMA_VISION_BASE", "http://ollama-vision:11434")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")

COMPREFACE_URL = os.getenv("COMPREFACE_URL", "http://compreface-api:8000")
COMPREFACE_API_KEY = os.getenv("COMPREFACE_API_KEY", "")

# Frigate integration
FRIGATE_MODE = os.getenv("FRIGATE_MODE", "false").lower() == "true"
FRIGATE_URL = os.getenv("FRIGATE_URL", "http://frigate:5000")
FRIGATE_CAMERA = os.getenv("FRIGATE_CAMERA", "webcam")
FRIGATE_POLL_INTERVAL = float(os.getenv("FRIGATE_POLL_INTERVAL", "2.0"))  # Poll every 2 seconds

# Webcam settings (used when FRIGATE_MODE=false)
WEBCAM_ENABLED = os.getenv("WEBCAM_ENABLED", "true").lower() == "true" and not FRIGATE_MODE
WEBCAM_DEVICE  = os.getenv("WEBCAM_DEVICE", "/dev/video0")
WEBCAM_WIDTH   = int(os.getenv("WEBCAM_WIDTH", "1920"))
WEBCAM_HEIGHT  = int(os.getenv("WEBCAM_HEIGHT", "1080"))
WEBCAM_FPS     = int(os.getenv("WEBCAM_FPS", "10"))

# K80 GPU preprocessing
K80_ENABLED = os.getenv("K80_ENABLED", "true").lower() == "true"
K80_DEVICE = os.getenv("K80_DEVICE", "cuda:3")  # GPU 3!
K80_SCENE_CHANGE_THRESHOLD = float(os.getenv("K80_SCENE_CHANGE_THRESHOLD", "0.3"))

# Detection processing interval
PROCESS_EVERY_N = int(os.getenv("PROCESS_EVERY_N", "3"))  # Process every N frames

# ---------------------- App ----------------------
app = FastAPI(title="Real-World Vision Gateway (Webcam + K80)")

# Global state
latest_frame: Dict[str, Any] = {}
recent_detections: List[Dict[str, Any]] = []
k80_processor = None
mjpeg_frame = None  # For MJPEG streaming

def b64_jpg(img: np.ndarray, q: int = 90) -> str:
    """Convert numpy image to base64 JPEG"""
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    return base64.b64encode(buf).decode("ascii") if ok else ""

def ha_event(event_type: str, data: Dict[str, Any]):
    """Send event to Home Assistant"""
    if not HA_BASE or not HA_TOKEN:
        return
    try:
        requests.post(
            f"{HA_BASE}/api/events/{event_type}",
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
            json=data, timeout=3.0
        )
    except Exception as e:
        print(f"HA event error: {e}", flush=True)

# ---------------------- Qwen-VL Call ----------------------
class QwenResponse(BaseModel):
    people_detected: int = 0
    activity: str = ""
    engagement: str = ""
    reasoning: str = ""

def call_qwen_vl(img: np.ndarray) -> Dict[str, Any]:
    """Call Qwen2.5-VL for deep scene analysis"""
    b64 = b64_jpg(img, 92)
    if not b64: return {}
    try:
        res = requests.post(
            f"{OLLAMA_VISION_BASE}/api/generate", timeout=45,
            json={
                "model": OLLAMA_VISION_MODEL,
                "format": "json",
                "stream": False,
                "images": [b64],
                "prompt": (
                    "You are an expert at analyzing real-world scenes with people. "
                    "Analyze this webcam image and provide: "
                    "1. Number of people visible "
                    "2. What they are doing (activity) "
                    "3. Their engagement level (focused/distracted/away) "
                    "4. Overall scene context. "
                    "Respond with JSON."
                ),
                "system": (
                    "You must respond in JSON format with fields: "
                    '`"people_detected": int`, `"activity": "brief description"`, '
                    '`"engagement": "engagement level"`, `"reasoning": "your analysis"`. '
                    'Do not include code fences.'
                )
            }
        )
        res.raise_for_status()
        body = res.json()
        return QwenResponse.model_validate_json(body.get("response", "{}")).model_dump()
    except Exception as e:
        print(f"Qwen-VL error: {e}", flush=True)
        return {"error": str(e)}

# ---------------------- CompreFace Integration ----------------------
def identify_faces(img: np.ndarray, face_boxes: List[List[int]]) -> List[Dict[str, Any]]:
    """
    Identify faces using CompreFace

    Args:
        img: Full image
        face_boxes: List of [x, y, w, h] face bounding boxes

    Returns:
        List of identification results
    """
    if not COMPREFACE_URL or not COMPREFACE_API_KEY:
        return []

    identifications = []
    for i, (x, y, w, h) in enumerate(face_boxes):
        try:
            # Crop face region
            face_crop = img[y:y+h, x:x+w]
            _, face_jpg = cv2.imencode(".jpg", face_crop)

            # Call CompreFace recognize endpoint
            res = requests.post(
                f"{COMPREFACE_URL}/api/v1/recognition/recognize",
                headers={"x-api-key": COMPREFACE_API_KEY},
                files={"file": ("face.jpg", face_jpg.tobytes(), "image/jpeg")},
                timeout=5.0
            )
            res.raise_for_status()
            data = res.json()

            # Extract best match
            if data.get("result") and len(data["result"]) > 0:
                match = data["result"][0]
                identifications.append({
                    "face_index": i,
                    "bbox": [x, y, w, h],
                    "subject": match.get("subjects", [{}])[0].get("subject", "Unknown"),
                    "confidence": match.get("similarity", 0.0)
                })
            else:
                identifications.append({
                    "face_index": i,
                    "bbox": [x, y, w, h],
                    "subject": "Unknown",
                    "confidence": 0.0
                })
        except Exception as e:
            print(f"CompreFace error for face {i}: {e}", flush=True)
            identifications.append({
                "face_index": i,
                "bbox": [x, y, w, h],
                "subject": "Error",
                "confidence": 0.0,
                "error": str(e)
            })

    return identifications

# ---------------------- Frigate Capture Loop ----------------------
def frigate_loop():
    """Poll Frigate for snapshots and process with K80"""
    global latest_frame, recent_detections, k80_processor, mjpeg_frame

    print(f"[frigate] Starting Frigate polling mode: {FRIGATE_URL}", flush=True)

    # Initialize K80 processor
    if K80_ENABLED:
        try:
            from app.k80_realworld_processor import K80RealWorldProcessor
            print(f"[frigate] Initializing K80 processor on {K80_DEVICE}...", flush=True)
            k80_processor = K80RealWorldProcessor(
                device=K80_DEVICE,
                scene_change_threshold=K80_SCENE_CHANGE_THRESHOLD
            )
            print("[frigate] K80 processor initialized successfully!", flush=True)
        except Exception as e:
            print(f"[frigate] WARNING: K80 processor failed to initialize: {e}", flush=True)
            print("[frigate] Continuing without K80 preprocessing", flush=True)

    frame_count = 0

    while True:
        try:
            # Fetch latest snapshot from Frigate
            response = requests.get(f"{FRIGATE_URL}/api/{FRIGATE_CAMERA}/latest.jpg", timeout=5)
            response.raise_for_status()

            # Decode image
            img_array = np.frombuffer(response.content, np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if frame is None:
                print("[frigate] Failed to decode frame", flush=True)
                time.sleep(FRIGATE_POLL_INTERVAL)
                continue

            frame_count += 1

            # Store latest frame for API access
            latest_frame["image_b64"] = b64_jpg(frame)
            latest_frame["timestamp"] = time.time()

            # Update MJPEG stream frame
            mjpeg_frame = frame.copy()

            # Process with K80 every N frames
            if k80_processor is not None and frame_count % PROCESS_EVERY_N == 0:
                try:
                    detections = k80_processor.process_frame(frame)

                    # Check for scene changes
                    if detections.get("scene_changed", False):
                        print(f"[frigate] Scene change detected, triggering Qwen analysis...", flush=True)

                        # Async Qwen analysis
                        def _qwen_analysis(img, dets):
                            try:
                                vl = call_qwen_vl(img)

                                # Identify faces if detected
                                face_ids = []
                                if dets.get("faces") and len(dets["faces"]) > 0:
                                    face_boxes = [f["bbox"] for f in dets["faces"]]
                                    face_ids = identify_faces(img, face_boxes)

                                # Send to HA
                                ha_event("vision.realworld_scene_change", {
                                    "source": "frigate_k80",
                                    "people_count": dets.get("people_count", 0),
                                    "face_count": dets.get("face_count", 0),
                                    "face_identifications": face_ids,
                                    "poses": dets.get("poses", []),
                                    "gestures": dets.get("gestures", []),
                                    "vl": vl,
                                    "ts": time.time()
                                })

                                # Store in recent detections
                                recent_detections.insert(0, {
                                    "timestamp": time.time(),
                                    "result": {
                                        "k80_detections": dets,
                                        "face_identifications": face_ids,
                                        "vl": vl,
                                        "detection_mode": "frigate_k80"
                                    },
                                    "frame_b64": b64_jpg(img, 85),
                                })
                                del recent_detections[10:]  # Keep last 10

                                print(f"[frigate] Analysis complete: {dets.get('people_count', 0)} people, {len(face_ids)} faces identified", flush=True)
                            except Exception as e:
                                print(f"[frigate] Qwen analysis error: {e}", flush=True)

                        threading.Thread(target=_qwen_analysis, args=(frame.copy(), detections), daemon=True).start()

                except Exception as e:
                    print(f"[frigate] K80 processing error: {e}", flush=True)

        except Exception as e:
            print(f"[frigate] Error fetching snapshot: {e}", flush=True)

        time.sleep(FRIGATE_POLL_INTERVAL)

# ---------------------- Webcam Capture Loop ----------------------
def webcam_loop():
    """Main webcam capture and processing loop"""
    global latest_frame, recent_detections, k80_processor, mjpeg_frame

    if not WEBCAM_ENABLED:
        print("[webcam] Not enabled, skipping.", flush=True)
        return

    # Initialize K80 processor if enabled
    if K80_ENABLED:
        try:
            from app.k80_realworld_processor import K80RealWorldProcessor
            print(f"[webcam] Initializing K80 processor on {K80_DEVICE}...", flush=True)
            k80_processor = K80RealWorldProcessor(
                device=K80_DEVICE,
                scene_change_threshold=K80_SCENE_CHANGE_THRESHOLD
            )
            print("[webcam] K80 processor initialized successfully!", flush=True)
        except Exception as e:
            print(f"[webcam] WARNING: K80 processor failed to initialize: {e}", flush=True)
            print("[webcam] Continuing without K80 preprocessing", flush=True)

    # Open webcam
    cap = cv2.VideoCapture(WEBCAM_DEVICE, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"[webcam] ERROR: Cannot open {WEBCAM_DEVICE}", flush=True)
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WEBCAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WEBCAM_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, WEBCAM_FPS)

    actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[webcam] Opened {WEBCAM_DEVICE} @ {actual_w}x{actual_h} {actual_fps}fps", flush=True)

    frame_count = 0
    delay = 1.0 / max(1, WEBCAM_FPS)

    while True:
        ok, frame = cap.read()
        if not ok:
            print("[webcam] Failed to read frame", flush=True)
            time.sleep(delay)
            continue

        frame_count += 1

        # Store latest frame for API access
        latest_frame["image_b64"] = b64_jpg(frame)
        latest_frame["timestamp"] = time.time()

        # Update MJPEG stream frame
        mjpeg_frame = frame.copy()

        # Process with K80 every N frames
        if k80_processor is not None and frame_count % PROCESS_EVERY_N == 0:
            try:
                detections = k80_processor.process_frame(frame)

                # Check for scene changes
                if detections.get("scene_changed", False):
                    print(f"[webcam] Scene change detected, triggering Qwen analysis...", flush=True)

                    # Async Qwen analysis
                    def _qwen_analysis(img, dets):
                        try:
                            vl = call_qwen_vl(img)

                            # Identify faces if detected
                            face_ids = []
                            if dets.get("faces") and len(dets["faces"]) > 0:
                                face_boxes = [f["bbox"] for f in dets["faces"]]
                                face_ids = identify_faces(img, face_boxes)

                            # Send to HA
                            ha_event("vision.realworld_scene_change", {
                                "source": "webcam_k80",
                                "people_count": dets.get("people_count", 0),
                                "face_count": dets.get("face_count", 0),
                                "face_identifications": face_ids,
                                "poses": dets.get("poses", []),
                                "gestures": dets.get("gestures", []),
                                "vl": vl,
                                "ts": time.time()
                            })

                            # Store in recent detections
                            recent_detections.insert(0, {
                                "timestamp": time.time(),
                                "result": {
                                    "k80_detections": dets,
                                    "face_identifications": face_ids,
                                    "vl": vl,
                                    "detection_mode": "k80_realworld"
                                },
                                "frame_b64": b64_jpg(img, 85),
                            })
                            del recent_detections[10:]  # Keep last 10

                            print(f"[webcam] Analysis complete: {dets.get('people_count', 0)} people, {len(face_ids)} faces identified", flush=True)
                        except Exception as e:
                            print(f"[webcam] Qwen analysis error: {e}", flush=True)

                    threading.Thread(target=_qwen_analysis, args=(frame.copy(), detections), daemon=True).start()

            except Exception as e:
                print(f"[webcam] K80 processing error: {e}", flush=True)

        time.sleep(delay)

@app.on_event("startup")
async def startup_event():
    """Start capture thread on startup"""
    if FRIGATE_MODE:
        print("Starting Frigate polling loop in background thread...", flush=True)
        frigate_thread = threading.Thread(target=frigate_loop, daemon=True)
        frigate_thread.start()
    elif WEBCAM_ENABLED:
        print("Starting webcam capture loop in background thread...", flush=True)
        webcam_thread = threading.Thread(target=webcam_loop, daemon=True)
        webcam_thread.start()
    else:
        print("No capture source enabled (Frigate and Webcam both disabled).", flush=True)

# ---------------------- HTTP API ----------------------
@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "webcam_enabled": WEBCAM_ENABLED,
        "k80_enabled": K80_ENABLED,
        "k80_initialized": k80_processor is not None
    }

@app.get("/api/detections")
def get_recent_detections():
    """Get recent detection results"""
    return recent_detections

@app.get("/api/latest_frame/{source}")
def get_latest_frame(source: str):
    """
    Get the latest frame from webcam

    Args:
        source: Source name (e.g., "webcam")

    Returns:
        JSON with base64-encoded image and timestamp
    """
    if source != "webcam" or not latest_frame:
        return {"error": f"No frames available for source '{source}'"}

    return {
        "image": latest_frame["image_b64"],
        "timestamp": latest_frame["timestamp"],
        "source": "webcam"
    }

@app.get("/stream/mjpeg")
async def mjpeg_stream():
    """
    Live MJPEG stream for Home Assistant

    Returns multipart MJPEG stream that can be consumed by HA's MJPEG camera platform
    """
    async def generate():
        while True:
            if mjpeg_frame is not None:
                # Encode frame as JPEG
                ok, jpeg = cv2.imencode(".jpg", mjpeg_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if ok:
                    frame_bytes = jpeg.tobytes()
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                    )
            await asyncio.sleep(0.1)  # ~10 FPS stream

    return Response(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/stream/latest.jpg")
async def latest_frame_jpg():
    """
    Latest frame as JPEG (for HA generic camera)

    Returns the most recent frame as a static JPEG image
    """
    if mjpeg_frame is not None:
        ok, jpeg = cv2.imencode(".jpg", mjpeg_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if ok:
            return Response(content=jpeg.tobytes(), media_type="image/jpeg")

    return Response(content=b"", status_code=404)

@app.get("/debug")
def debug_page():
    """Debug page showing latest detection"""
    global recent_detections
    if not recent_detections:
        from fastapi.responses import HTMLResponse
        return HTMLResponse("<html><body>No detections yet.</body></html>")

    latest = recent_detections[0]
    img_b64 = latest.get("frame_b64")
    res = latest.get("result", {})

    from fastapi.responses import HTMLResponse
    return HTMLResponse(f"""
    <html><head><title>Real-World Vision Debug</title></head><body>
    <h1>Latest Detection</h1>
    <p>Timestamp: {datetime.fromtimestamp(latest.get('timestamp', 0))}</p>
    <pre>{res}</pre>
    <img src="data:image/jpeg;base64,{img_b64}" style="max-width: 80vw;"/>
    </body></html>
    """)

# ---------------------- Main ----------------------
if __name__ == "__main__":
    import uvicorn
    import asyncio
    uvicorn.run(app, host="0.0.0.0", port=8089)
