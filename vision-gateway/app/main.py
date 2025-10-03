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

# Keywords we care about
SEED_WORDS = [r"accept", r"decline", r"join(?:\s+now)?", r"send(?:\s+update)?", r"meeting", r"invite", r"calendar"]
TIME_PAT = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d(\s?[APap]\.?M\.?)?\b")
DATE_PAT = re.compile(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\,?\s?(?:\d{1,2}\/\d{1,2}|\d{4}-\d{2}-\d{2}|\w+\s+\d{1,2})\b")

# OCR engine (EN first; add 'lang' list if you want more)
ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)

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
        pressed = (s < 0.70) or (dv < -0.12) or (dcontrast < -0.20) or (dedge < -0.15)
        now = time.time()
        sustained = pressed and (now - self.last_pressed_ts > 0.5)
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
      "app (Teams/Zoom/Meet/Unknown), invite_detected (true/false), title, start_iso if present, "
      "buttons (array), and action_state (one of: pending/accepted/declined/joined/none). "
      "Return strict minified JSON with keys: app, invite_detected, title, start_iso, buttons, action_state, confidence."
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
        return {"app":"Unknown","invite_detected":False,"title":"","start_iso":"","buttons":[],"action_state":"none","confidence":0.0}
    except Exception:
        return {"app":"Unknown","invite_detected":False,"title":"","start_iso":"","buttons":[],"action_state":"none","confidence":0.0}

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
    for b in boxes:
        t = b["text"].lower()
        if re.search(r"\b(accept|join|decline|send)\b", t):
            # expand a bit and start tracker for this source
            x,y,w,h = b["bbox"]; pad = int(max(w,h)*0.5)
            x,y = max(0,x-pad), max(0,y-pad)
            w,h = min(frame_ds.shape[1]-x, w+2*pad), min(frame_ds.shape[0]-y, h+2*pad)
            _trackers[source] = ROITracker(frame_ds, (x,y,w,h))
            break

    # Call VL to interpret (optional but recommended)
    vl = call_qwen_vl(frame_ds, crops)

    # Push HA events
    if vl.get("invite_detected"):
        ha_event("vision.meeting_invite", {
            "source": source,
            "app": vl.get("app","Unknown"),
            "title": vl.get("title",""),
            "start_iso": vl.get("start_iso",""),
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

if HDMI_ENABLED:
    threading.Thread(target=hdmi_loop, daemon=True).start()
