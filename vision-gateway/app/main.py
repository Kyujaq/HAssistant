import base64, io, os, re, time, threading
from typing import List, Optional, Dict, Any, Tuple
import requests
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
import numpy as np
import cv2
from skimage.metrics import structural_similarity as ssim
from paddleocr import PaddleOCR

HA_BASE = os.getenv("HA_BASE_URL", "")
HA_TOKEN = os.getenv("HA_TOKEN", "")
OLLAMA_VISION_BASE = os.getenv("OLLAMA_VISION_BASE", "http://ollama-vision:11434")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")

HDMI_ENABLED = os.getenv("HDMI_ENABLED", "false").lower() == "true"
HDMI_DEVICE = os.getenv("HDMI_DEVICE", "/dev/video0")
HDMI_FPS = float(os.getenv("HDMI_FPS", "2"))
HDMI_RESIZE_LONG = int(os.getenv("HDMI_RESIZE_LONG", "1280"))

MOTION_THRESHOLD = float(os.getenv("MOTION_THRESHOLD", "0.015"))  # fraction of pixels changed
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "8"))
OCR_MODE = os.getenv("OCR_MODE", "anchor_based")  # anchor_based or full_screen

# Keywords we care about
SEED_WORDS = [r"accept", r"decline", r"send(?:\s+update)?", r"meeting", r"invite", r"calendar"]
TIME_PAT = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d(\s?[APap]\.?M\.?)?\b")
DATE_PAT = re.compile(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\,?\s?(?:\d{1,2}\/\d{1,2}|\d{4}-\d{2}-\d{2}|\w+\s+\d{1,2})\b")

# OCR engine (EN first; add 'lang' list if you want more)
# Optimized for speed: disable angle classification, faster detection threshold
ocr = PaddleOCR(use_angle_cls=False, lang='en', show_log=False, det_db_thresh=0.3)

app = FastAPI(title="Vision Gateway")

# ---- State for button tracking ----
class ROITracker:
    def __init__(self, frame: np.ndarray, bbox: Tuple[int,int,int,int]):
        x,y,w,h = bbox
        self.bbox = [x,y,w,h]
        self.tracker = cv2.legacy.TrackerCSRT_create()
        self.tracker.init(frame, tuple(self.bbox))
        crop = frame[y:y+h, x:x+w]
        self.baseline = self._features(crop)
        self.last_pressed_ts = 0.0
        self.init_time = time.time()  # Track when tracker was created

    def _features(self, crop):
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mean_hsv = hsv.reshape(-1,3).mean(0)
        # edge energy
        edges = cv2.Laplacian(gray, cv2.CV_32F)
        edge_energy = float(np.mean(np.abs(edges)))
        # contrast proxy
        contrast = float(gray.std())
        return {"mean_hsv": mean_hsv, "edge": edge_energy, "contrast": contrast, "gray": gray}

    def update_and_check(self, frame) -> Dict[str,Any]:
        ok, box = self.tracker.update(frame)
        if not ok:
            return {"ok": False, "pressed": False, "lost": True}
        x,y,w,h = [int(v) for v in box]
        crop = frame[y:y+h, x:x+w]
        f = self._features(crop)
        # SSIM with baseline
        s = ssim(self.baseline["gray"], f["gray"], data_range=255)
        dv = float((f["mean_hsv"][2] - self.baseline["mean_hsv"][2]) / max(1.0, self.baseline["mean_hsv"][2]))
        dcontrast = float((f["contrast"] - self.baseline["contrast"]) / max(1.0, self.baseline["contrast"]))
        dedge = float((f["edge"] - self.baseline["edge"]) / max(1.0, self.baseline["edge"]))
        # More conservative thresholds to avoid false positives
        pressed = (s < 0.60) or (dv < -0.20) or (dcontrast < -0.30) or (dedge < -0.25)
        now = time.time()

        # Warmup period: ignore presses for first 2 seconds after tracker init
        if (now - self.init_time) < 2.0:
            return {"ok": True, "pressed": False, "bbox":[x,y,w,h], "ssim":s, "dv":dv, "warmup": True}

        sustained = pressed and (now - self.last_pressed_ts > 1.0)  # Require 1s sustained press
        if pressed:
            self.last_pressed_ts = now
        return {"ok": True, "pressed": sustained, "bbox":[x,y,w,h], "ssim":s, "dv":dv, "dcontrast":dcontrast, "dedge":dedge}

_trackers: Dict[str, ROITracker] = {}  # key: source -> tracker

def ha_event(event_type: str, data: Dict[str,Any]):
    if not HA_BASE or not HA_TOKEN:
        return
    try:
        requests.post(
            f"{HA_BASE}/api/events/{event_type}",
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type":"application/json"},
            json=data, timeout=2.5
        )
    except Exception:
        pass

def b64_jpg(img: np.ndarray) -> str:
    _, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return base64.b64encode(buf.tobytes()).decode("ascii")

def downscale_keep_long(img: np.ndarray, long_side: int) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h,w) <= long_side: return img
    if h >= w:
        new_h = long_side
        new_w = int(w * long_side / h)
    else:
        new_w = long_side
        new_h = int(h * long_side / w)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

def motion_changed(prev_gray, gray) -> float:
    # MOG2 would need persistent background; simple frame diff is fine at low FPS
    diff = cv2.absdiff(prev_gray, gray)
    _, th = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    changed = np.count_nonzero(th) / th.size
    return changed

def ocr_with_boxes(img: np.ndarray):
    # PaddleOCR returns [ [ [box_pts], (text, conf) ], ... ]
    res = ocr.ocr(img, cls=True)
    boxes = []
    if not res: return boxes
    for line in res:
        for det in line:
            pts = det[0]  # 4 points
            (text, conf) = det[1]
            x_coords = [p[0] for p in pts]
            y_coords = [p[1] for p in pts]
            x, y, w, h = int(min(x_coords)), int(min(y_coords)), int(max(x_coords)-min(x_coords)), int(max(y_coords)-min(y_coords))
            boxes.append({"bbox":[x,y,w,h], "text":text, "conf":float(conf)})
    return boxes

def smart_crops(img: np.ndarray, boxes) -> List[Dict[str,Any]]:
    H, W = img.shape[:2]
    seeds = []
    for b in boxes:
        t = b["text"].lower()
        if any(re.search(sw, t) for sw in SEED_WORDS):
            x,y,w,h = b["bbox"]
            pad = int(max(w,h)*1.5)
            x0 = max(0, x - pad); y0 = max(0, y - pad)
            x1 = min(W, x + w + pad); y1 = min(H, y + h + pad)
            seeds.append([x0,y0,x1-x0,y1-y0])
    # merge overlaps
    merged = []
    for s in seeds:
        merged_flag = False
        for m in merged:
            mx,my,mw,mh = m; sx,sy,sw,sh = s
            if not (sx > mx+mw or mx > sx+sw or sy > my+mh or my > sy+sh):
                nx0 = min(mx,sx); ny0=min(my,sy)
                nx1 = max(mx+mw, sx+sw); ny1=max(my+mh, sy+sh)
                m[:] = [nx0,ny0,nx1-nx0,ny1-ny0]
                merged_flag = True; break
        if not merged_flag: merged.append(s)
    # score with simple heuristics
    scored = []
    for x,y,w,h in merged or [[0,0,W,H]]:  # fallback full frame
        crop = img[y:y+h, x:x+w]
        text_hits = sum(1 for b in boxes if (x<=b["bbox"][0]<=x+w and y<=b["bbox"][1]<=y+h) and (TIME_PAT.search(b["text"]) or DATE_PAT.search(b["text"]) or any(re.search(sw, b["text"].lower()) for sw in SEED_WORDS)))
        score = text_hits + 0.1*(w*h)/(W*H)
        scored.append({"bbox":[x,y,w,h], "score":score, "b64": b64_jpg(crop)})
    scored.sort(key=lambda d: d["score"], reverse=True)
    return scored[:3]

def call_qwen_vl(full_img: np.ndarray, crops: List[Dict[str,Any]]) -> Dict[str,Any]:
    # Build multi-image prompt
    prompt = (
      "You are a UI vision agent. From these images (first is full frame, others are crops), "
      "determine if there is a meeting invite/join dialog. Extract: "
      "app (Teams/Zoom/Meet/Unknown), invite_detected (true/false), title, attendees, start_iso, end_iso if present, "
      "buttons (array), and action_state (one of: pending/accepted/declined/joined/none). "
      "Return strict minified JSON with keys: app, invite_detected, title, attendees, start_iso, end_iso buttons, action_state, confidence."
    )
    images = [b64_jpg(full_img)] + [c["b64"] for c in crops]
    try:
        r = requests.post(f"{OLLAMA_VISION_BASE}/api/generate",
                          json={"model": OLLAMA_VISION_MODEL, "prompt": prompt, "images": images, "stream": False},
                          timeout=30)
        r.raise_for_status()
        # Ollama returns {"response": "..."} plain text
        txt = r.json().get("response","").strip()
        # Try to find JSON in response
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            import json
            return json.loads(m.group(0))
        return {"app":"Unknown","invite_detected":False,"title":"","attendees":"","start_iso":"","end_iso":"","buttons":[],"action_state":"none","confidence":0.0}
    except Exception:
        return {"app":"Unknown","invite_detected":False,"title":"","attendees":"","start_iso":"","end_iso":"","buttons":[],"action_state":"none","confidence":0.0}

last_motion_ts: Dict[str,float] = {"hdmi":0.0}
prev_gray_map: Dict[str,np.ndarray] = {}

def process_frame(source: str, frame: np.ndarray) -> Dict[str,Any]:
    # Downscale for speed
    frame_ds = downscale_keep_long(frame, HDMI_RESIZE_LONG if source=="hdmi" else 1280)
    gray = cv2.cvtColor(frame_ds, cv2.COLOR_BGR2GRAY)
    # Motion gating
    changed = 1.0
    if source in prev_gray_map:
        changed = motion_changed(prev_gray_map[source], gray)
    prev_gray_map[source] = gray
    now = time.time()
    if changed < MOTION_THRESHOLD and (now - last_motion_ts.get(source, 0)) < COOLDOWN_SECONDS:
        return {"skipped":"no_motion"}
    if changed >= MOTION_THRESHOLD:
        last_motion_ts[source] = now

    # OCR
    boxes = ocr_with_boxes(frame_ds)
    if not boxes:
        return {"invite_detected": False, "boxes": 0}

    # Smart crops
    crops = smart_crops(frame_ds, boxes)

    # If we see an action word, lock tracker
    #for b in boxes:
    #    t = b["text"].lower()
    #    if re.search(r"\b(accept|decline|send)\b", t):
    #        # expand a bit and start tracker for this source
    #        x,y,w,h = b["bbox"]; pad = int(max(w,h)*0.5)
    #        x,y = max(0,x-pad), max(0,y-pad)
    #        w,h = min(frame_ds.shape[1]-x, w+2*pad), min(frame_ds.shape[0]-y, h+2*pad)
    #       _trackers[source] = ROITracker(frame_ds, (x,y,w,h))
    #        break

    # Call VL to interpret (optional but recommended)
    vl = call_qwen_vl(frame_ds, crops)

    # Push HA events
    if vl.get("invite_detected"):
        ha_event("vision.meeting_invite", {
            "source": source,
            "app": vl.get("app","Unknown"),
            "title": vl.get("title",""),
            "attendees": vl.get("attendees",""),
            "start_iso": vl.get("start_iso",""),
            "end_iso": vl.get("end_iso",""),
            "buttons": vl.get("buttons",[]),
            "confidence": vl.get("confidence",0.0)
        })

    return {"invite_detected": vl.get("invite_detected", False), "vl": vl, "crops": [{"bbox":c["bbox"],"score":c["score"]} for c in crops]}

@app.post("/ingest_frame")
async def ingest_frame(source: str = Form(...), file: UploadFile = File(...)):
    img_bytes = await file.read()
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    res = process_frame(source, img)
    return res

class TrackInput(BaseModel):
    source: str

@app.post("/poll_tracking")
def poll_tracking(inp: TrackInput):
    source = inp.source
    if source not in _trackers:
        return {"tracking": False}
    # For poll mode you must POST frames via /ingest_frame; or for HDMI pull use internal loop
    return {"tracking": True}

# ---- Optional: internal HDMI reader loop ----
def hdmi_loop():
    cap = cv2.VideoCapture(HDMI_DEVICE, cv2.CAP_V4L2)
    # You can set formats if needed, e.g., cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    if not cap.isOpened():
        print("[hdmi] cannot open device", HDMI_DEVICE, flush=True); return
    delay = 1.0/max(0.1, HDMI_FPS)
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.1); continue
        res = process_frame("hdmi", frame)
        # If we are tracking a button, do a quick press check on the same frame
        if "hdmi" in _trackers:
            tr = _trackers["hdmi"].update_and_check(downscale_keep_long(frame, HDMI_RESIZE_LONG))
            if tr.get("pressed"):
                ha_event("vision.meeting_action", {
                    "source":"hdmi","action":"button_press","state":"pressed",
                    "metrics":{"ssim":tr["ssim"],"dv":tr["dv"],"dcontrast":tr["dcontrast"],"dedge":tr["dedge"]},
                    "bbox":tr.get("bbox"), "ts": time.time()
                })
        time.sleep(delay)

@app.get("/healthz")
def healthz():
    return {"ok": True}

# ---- Debug endpoints and Frigate stream integration ----
recent_detections = []  # Store last 10 detections

def frigate_stream_loop_legacy():
    """Legacy full-screen OCR mode (original implementation)"""
    FRIGATE_API = "http://frigate:5000/api/ugreen_camera/latest.jpg"

    while True:
        try:
            # Fetch latest frame from Frigate
            resp = requests.get(FRIGATE_API, timeout=5)
            if resp.status_code != 200:
                print(f"[frigate_stream] Failed to fetch frame: {resp.status_code}", flush=True)
                time.sleep(5)
                continue

            # Decode image
            img_array = np.frombuffer(resp.content, np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if frame is None:
                time.sleep(5)
                continue

            # Process frame
            result = process_frame("frigate_hdmi", frame)

            # Store detection if interesting
            if result.get("invite_detected") or result.get("vl", {}).get("invite_detected"):
                recent_detections.insert(0, {
                    "timestamp": time.time(),
                    "result": result,
                    "frame_b64": b64_jpg(cv2.resize(frame, (640, 360)))  # Small preview
                })
                recent_detections[:] = recent_detections[:10]  # Keep last 10

            time.sleep(10)  # Process 0.1 FPS (every 10 seconds - reduce CPU load)

        except Exception as e:
            print(f"[frigate_stream] Error: {e}", flush=True)
            time.sleep(5)

def frigate_stream_loop():
    """
    Press-triggered detection loop (ultra CPU efficient)

    Phase 1: Lightweight OCR to find buttons
    Phase 2: Track button visually (no OCR, just pixel changes)
    Phase 3: On button press (darkening) → snapshot + full context extraction
    Phase 4: Vision model only when button is pressed
    """
    from . import anchor_detector

    # Share OCR instance with anchor detector to avoid creating multiple instances
    anchor_detector.set_shared_ocr(ocr)

    # Toggle between modes
    if OCR_MODE == "full_screen":
        print("[frigate_stream] Using legacy full-screen OCR mode", flush=True)
        return frigate_stream_loop_legacy()

    print("[frigate_stream] Using press-triggered detection mode", flush=True)
    FRIGATE_API = "http://frigate:5000/api/ugreen_camera/latest.jpg"

    button_tracker = None  # Track button visually
    tracking_source = "frigate_hdmi"

    while True:
        try:
            # Fetch latest frame from Frigate
            resp = requests.get(FRIGATE_API, timeout=5)
            if resp.status_code != 200:
                print(f"[frigate_stream] Failed to fetch frame: {resp.status_code}", flush=True)
                time.sleep(5)
                continue

            # Decode image
            img_array = np.frombuffer(resp.content, np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if frame is None:
                time.sleep(5)
                continue

            # Downscale for faster processing
            frame_ds = downscale_keep_long(frame, HDMI_RESIZE_LONG)

            # Crop to left half for button detection (buttons are typically on left)
            h, w = frame_ds.shape[:2]
            left_half = frame_ds[:, :w//4]  # Left 50% of screen

            # If we're tracking a button, check for press
            if button_tracker is not None:
                track_result = button_tracker.update_and_check(frame_ds)

                if not track_result.get("ok"):
                    # Lost tracking, reset
                    print("[frigate_stream] Lost button tracking, rescanning...", flush=True)
                    button_tracker = None
                    time.sleep(2)
                    continue

                if track_result.get("pressed"):
                    # ===== BUTTON PRESSED! Capture snapshot and run Qwen analysis =====
                    print(f"[frigate_stream] 🔥 BUTTON PRESS DETECTED! Running Qwen analysis...", flush=True)

                    # Use the tracker's bbox (already knows where the button is)
                    tracked_bbox = track_result["bbox"]

                    # Run OCR and Qwen VL analysis (Qwen extracts everything we need)
                    ocr_boxes = ocr_with_boxes(frame_ds)
                    crops = smart_crops(frame_ds, ocr_boxes)
                    vl_result = call_qwen_vl(frame_ds, crops)

                    # Create button info from tracked bbox
                    button_info = {
                        "bbox": tracked_bbox,
                        "keyword": "button",
                        "text": "Tracked Button"
                    }

                    # Push HA event with Qwen's data only
                    ha_event("vision.meeting_action", {
                        "source": tracking_source,
                        "action": "button_press",
                        "button": button_info["keyword"],
                        "vl": vl_result,
                        "metrics": {"ssim": track_result["ssim"], "dv": track_result["dv"]}
                    })

                    # Store detection
                    result = {
                        "invite_detected": vl_result.get("invite_detected", False),
                        "button_pressed": True,
                        "vl": vl_result,
                        "anchor_button": button_info,
                        "detection_mode": "press_triggered"
                    }

                    # Store full-resolution image and coordinates (no scaling)
                    # Browser will handle display scaling via CSS
                    recent_detections.insert(0, {
                        "timestamp": time.time(),
                        "result": result,
                        "frame_b64": b64_jpg(frame_ds),
                        "button_bbox": tracked_bbox
                    })
                    recent_detections[:] = recent_detections[:10]

                    print(f"[frigate_stream] ✅ Press captured! Qwen detected: {vl_result.get('invite_detected', False)}, title='{vl_result.get('title', '')[:40]}'", flush=True)

                    # Reset tracker after press
                    button_tracker = None
                    time.sleep(5)  # Cooldown after press
                else:
                    # Still tracking, no press yet
                    time.sleep(1.0)  # Poll at 1 FPS when tracking (balance speed vs CPU)
                continue

            # ===== Phase 1: Lightweight scan for buttons (no tracking yet) =====
            # Scan only left half for better performance
            ocr_boxes = ocr_with_boxes(left_half)

            if not ocr_boxes:
                time.sleep(5)
                continue

            buttons = anchor_detector.detect_buttons(left_half, ocr_boxes=ocr_boxes)

            if buttons:
                # Found button! Start tracking it
                priority_order = ["accept", "decline", "send"]
                buttons_sorted = sorted(buttons, key=lambda b: priority_order.index(b["keyword"]) if b["keyword"] in priority_order else 999)
                primary_button = buttons_sorted[0]

                print(f"[frigate_stream] 👁️  Found {primary_button['keyword']} button at ({primary_button['bbox'][0]}, {primary_button['bbox'][1]}), starting visual tracking...", flush=True)

                # Initialize tracker on this button (use full frame for tracking)
                x, y, w, h = primary_button["bbox"]
                button_tracker = ROITracker(frame_ds, (x, y, w, h))

                time.sleep(3)  # Wait longer before checking press to avoid false positives
            else:
                # No buttons, keep scanning
                time.sleep(5)

        except Exception as e:
            print(f"[frigate_stream] Error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            button_tracker = None
            time.sleep(5)

@app.get("/debug")
async def debug_page():
    """HTML debug UI with anchor detection visualization"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Vision Gateway Debug - Anchor Detection</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body { font-family: monospace; background: #1a1a1a; color: #0f0; padding: 20px; }
            .header { border-bottom: 2px solid #0f0; margin-bottom: 20px; padding-bottom: 10px; }
            .mode { color: #ff0; font-size: 1.2em; }
            .detection { border: 1px solid #0f0; margin: 20px 0; padding: 15px; background: #0a0a0a; }
            .timestamp { color: #0ff; font-size: 1.1em; margin-bottom: 10px; }
            .image-container { position: relative; display: inline-block; }
            img { max-width: 640px; border: 1px solid #0f0; }
            canvas { position: absolute; top: 0; left: 0; max-width: 640px; pointer-events: none; }
            .context-info { color: #ff0; margin: 10px 0; }
            .context-text { background: #000; padding: 5px; margin: 5px 0; border-left: 3px solid #0ff; }
            pre { background: #000; padding: 10px; overflow-x: auto; }
            .button-info { color: #0f0; font-weight: bold; }
            .legend { margin: 20px 0; padding: 10px; background: #000; border: 1px solid #0f0; }
            .legend-item { margin: 5px 0; }
            .legend-box { display: inline-block; width: 20px; height: 10px; margin-right: 10px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Vision Gateway - Anchor-Based Detection</h1>
            <p class="mode">Mode: """ + OCR_MODE + """</p>
            <p>Monitoring Frigate HDMI stream for meeting invites...</p>
        </div>
        <div class="legend">
            <div class="legend-item"><span class="legend-box" style="background: #00ff00;"></span>Button Detection (Press Trigger)</div>
        </div>
        <div id="detections"></div>
        <script>
            function drawBoundingBoxes(imgElement, buttonBbox) {
                console.log('drawBoundingBoxes called', {buttonBbox, imgNaturalWidth: imgElement.naturalWidth, imgNaturalHeight: imgElement.naturalHeight});

                const container = imgElement.parentElement;

                // Remove any existing canvas
                const existingCanvas = container.querySelector('canvas');
                if (existingCanvas) existingCanvas.remove();

                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');

                // Canvas internal size matches image natural size
                // Coordinates from Python are already in this space
                canvas.width = imgElement.naturalWidth;
                canvas.height = imgElement.naturalHeight;

                // CSS size matches the displayed image size
                canvas.style.width = '100%';
                canvas.style.height = '100%';
                canvas.style.position = 'absolute';
                canvas.style.top = '0';
                canvas.style.left = '0';
                canvas.style.pointerEvents = 'none';

                console.log('Canvas created:', {width: canvas.width, height: canvas.height});

                // Draw button bbox (green)
                if (buttonBbox && buttonBbox.length === 4) {
                    const [x, y, w, h] = buttonBbox;
                    ctx.strokeStyle = '#00ff00';
                    ctx.lineWidth = 4;
                    ctx.strokeRect(x, y, w, h);
                    ctx.fillStyle = '#00ff00';
                    ctx.font = '14px monospace';
                    ctx.fillText('BUTTON', x, Math.max(y - 5, 12));
                }

                container.appendChild(canvas);
            }

            fetch('/api/detections')
                .then(r => r.json())
                .then(data => {
                    const div = document.getElementById('detections');
                    if (data.length === 0) {
                        div.innerHTML = '<p>No detections yet... Waiting for meeting invites...</p>';
                        return;
                    }
                    div.innerHTML = data.map(d => {
                        const buttonInfo = d.button_bbox ? `<p class="button-info">Button: ${JSON.stringify(d.result.anchor_button || {})}</p>` : '';
                        const vl = d.result.vl || {};
                        const qwenInfo = vl.invite_detected ? `
                            <div class="context-info">
                                <h3>Qwen VL Extraction:</h3>
                                ${vl.app ? '<div class="context-text"><strong>App:</strong> ' + vl.app + '</div>' : ''}
                                ${vl.title ? '<div class="context-text"><strong>Title:</strong> ' + vl.title + '</div>' : ''}
                                ${vl.start_iso ? '<div class="context-text"><strong>Start:</strong> ' + vl.start_iso + '</div>' : ''}
                                ${vl.end_iso ? '<div class="context-text"><strong>End:</strong> ' + vl.end_iso + '</div>' : ''}
                                ${vl.location ? '<div class="context-text"><strong>Location:</strong> ' + vl.location + '</div>' : ''}
                                ${vl.attendees ? '<div class="context-text"><strong>Attendees:</strong> ' + vl.attendees + '</div>' : ''}
                                ${vl.action_state ? '<div class="context-text"><strong>State:</strong> ' + vl.action_state + '</div>' : ''}
                            </div>
                        ` : '';

                        // Add unique ID for debugging
                        const imgId = 'img_' + d.timestamp;

                        return `
                            <div class="detection">
                                <div class="timestamp">${new Date(d.timestamp * 1000).toLocaleString()}</div>
                                ${buttonInfo}
                                <div class="image-container" style="position: relative; display: inline-block;">
                                    <img id="${imgId}" src="data:image/jpeg;base64,${d.frame_b64}"
                                         style="display: block; max-width: 100%; height: auto;"
                                         onload='console.log("Image loaded:", "${imgId}"); drawBoundingBoxes(this, ${JSON.stringify(d.button_bbox)})'
                                         onerror='console.error("Image failed to load:", "${imgId}")'>
                                </div>
                                ${qwenInfo}
                                <details>
                                    <summary>Full Detection Data (Qwen VL)</summary>
                                    <pre>${JSON.stringify(d.result, null, 2)}</pre>
                                </details>
                            </div>
                        `;
                    }).join('');
                });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/api/detections")
def get_recent_detections():
    """API endpoint for recent detections"""
    return recent_detections

from fastapi.responses import HTMLResponse

# Start Frigate stream processor
threading.Thread(target=frigate_stream_loop, daemon=True).start()

if HDMI_ENABLED:
    threading.Thread(target=hdmi_loop, daemon=True).start()
