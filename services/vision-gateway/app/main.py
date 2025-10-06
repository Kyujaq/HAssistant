import base64, io, os, re, time, threading
from typing import List, Optional, Dict, Any, Tuple
import requests
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
import numpy as np
import cv2
from skimage.metrics import structural_similarity as ssim
from paddleocr import PaddleOCR
from fastapi.responses import HTMLResponse
from collections import deque

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
    def __init__(self, frame: np.ndarray, bbox: Tuple[int,int,int,int], icon_edges: np.ndarray | None = None):
        x,y,w,h = bbox
        self.bbox = [x,y,w,h]
        self.tracker = cv2.legacy.TrackerCSRT_create()
        self.tracker.init(frame, tuple(self.bbox))
        crop = frame[y:y+h, x:x+w]
        self.baseline = self._features(crop)
        self.init_time = time.time()  # Track when tracker was created

        # Icon template edges (optional) and baseline score
        self.icon_edges = icon_edges
        self.base_icon_score = self._icon_score(self.baseline["gray"]) if icon_edges is not None else None

        # Short history to tolerate choppy/low-bw streams
        self._ssim_hist = deque(maxlen=3)
        self._icon_hist = deque(maxlen=3)

        # --- background box: slightly larger area around the ROI (for global-change suppression)
        H, W = frame.shape[:2]
        x,y,w,h = self.bbox
        scale = 1.8
        bg_w = int(w*scale); bg_h = int(h*scale)
        bg_x = max(0, x - (bg_w - w)//2); bg_y = max(0, y - (bg_h - h)//2)
        bg_w = min(W - bg_x, bg_w); bg_h = min(H - bg_y, bg_h)
        self.bg_box = [bg_x, bg_y, bg_w, bg_h]
        bg0 = frame[bg_y:bg_y+bg_h, bg_x:bg_x+bg_w]
        self.bg_gray0 = cv2.cvtColor(bg0, cv2.COLOR_BGR2GRAY)

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

    def _icon_score(self, gray_roi: np.ndarray) -> float:
        if self.icon_edges is None:
            return 1.0
        roi_edges = cv2.Canny(gray_roi, 50, 150)
        th0, tw0 = self.icon_edges.shape[:2]
        gh, gw = roi_edges.shape[:2]
        if tw0 == 0 or th0 == 0 or gw == 0 or gh == 0:
            return 0.0
        s = min(1.2, max(0.5, min(gw/float(tw0), gh/float(th0))))
        tmpl = cv2.resize(self.icon_edges, (max(8,int(tw0*s)), max(8,int(th0*s))), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(roi_edges, tmpl, cv2.TM_CCOEFF_NORMED)
        return float(res.max()) if res.size else 0.0

    def update_and_check(self, frame) -> Dict[str,Any]:
        ok, box = self.tracker.update(frame)
        if not ok:
            return {"ok": False, "pressed": False, "lost": True}
        x,y,w,h = [int(v) for v in box]
        crop = frame[y:y+h, x:x+w]
        f = self._features(crop)

        # SSIM vs baseline (resize-safe)
        gray0 = cv2.resize(self.baseline["gray"], (f["gray"].shape[1], f["gray"].shape[0]))
        s = ssim(gray0, f["gray"], data_range=255)

        dv = float((f["mean_hsv"][2] - self.baseline["mean_hsv"][2]) / max(1.0, self.baseline["mean_hsv"][2]))
        dcontrast = float((f["contrast"] - self.baseline["contrast"]) / max(1.0, self.baseline["contrast"]))
        dedge = float((f["edge"] - self.baseline["edge"]) / max(1.0, self.baseline["edge"]))

        icon_score = self._icon_score(f["gray"]) if self.icon_edges is not None else None
        icon_drop = None
        if self.base_icon_score is not None and icon_score is not None:
            icon_drop = float(self.base_icon_score - icon_score)

        # Background SSIM to detect global scene changes (minimize/open)
        bg_x, bg_y, bg_w, bg_h = self.bg_box
        bg_cur = frame[bg_y:bg_y+bg_h, bg_x:bg_x+bg_w]
        bg_gray = cv2.cvtColor(bg_cur, cv2.COLOR_BGR2GRAY)
        bg0_resized = cv2.resize(self.bg_gray0, (bg_gray.shape[1], bg_gray.shape[0]))
        s_bg = ssim(bg0_resized, bg_gray, data_range=255)

        now = time.time()
        if (now - self.init_time) < 0.6:
            # Warmup period: ignore presses briefly
            return {
                "ok": True, "pressed": False, "bbox":[x,y,w,h],
                "ssim":s, "ssim_bg": s_bg, "dv":dv, "icon":icon_score, "warmup": True
            }

        # --- Record short history (3 frames) ---
        self._ssim_hist.append(s)
        if icon_score is not None:
            self._icon_hist.append(icon_score)

        # Reject obvious minimize: huge global darkening
        if dv < -0.50:
            return {
                "ok": True, "pressed": False, "bbox":[x,y,w,h],
                "ssim":s, "ssim_bg": s_bg, "dv":dv, "icon":icon_score, "minimized": True
            }

        # --- Press heuristics ---
        # A) Icon score drops noticeably or under a floor (sensitive to tiny glyph changes)
        pressed_by_icon = False
        if icon_score is not None:
            pressed_by_icon = (icon_score < 0.58) or (icon_drop is not None and icon_drop > 0.10)

        # B) SSIM indicates small, consistent ROI change (does not require darkening)
        pressed_by_ssim = (s < 0.88) and (abs(dv) > 0.03 or dcontrast < -0.08)

        # C) Vote: 2-of-3 frames look pressed (icon or SSIM)
        votes = 0
        votes += sum(1 for v in list(self._icon_hist) if v < 0.58) if self._icon_hist else 0
        votes += sum(1 for v in list(self._ssim_hist) if v < 0.88)
        pressed_by_vote = (votes >= 2)

        # If background changed a lot too, treat as global change (open/minimize), not a press
        global_change = (s_bg < 0.85)

        pressed = (not global_change) and bool(pressed_by_icon or pressed_by_ssim or pressed_by_vote)

        return {
            "ok": True,
            "pressed": pressed,
            "bbox":[x,y,w,h],
            "ssim": s,
            "ssim_bg": s_bg,
            "dv": dv,
            "dcontrast": dcontrast,
            "dedge": dedge,
            "icon": icon_score,
            "icon_drop": icon_drop,
            "global_change": global_change,
        }

_trackers: Dict[str, ROITracker] = {}  # key: source -> tracker

# ---- icon templates (generic) ----
ICON_PATHS = {
    "send": "/app/assets/send.png",
    "accept": "/app/assets/accept.png",
    # "tentative": "/app/assets/tentative.png",
    # "decline": "/app/assets/decline.png",
    # "cancel": "/app/assets/cancel.png",
}
ICON_EDGES = {}

def _load_icon_edges():
    ICON_EDGES.clear()
    for k, p in ICON_PATHS.items():
        if not os.path.exists(p):  # skip missing files silently
            continue
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        ICON_EDGES[k] = cv2.Canny(img, 50, 150)
    print(f"[icons] loaded: {list(ICON_EDGES.keys())}", flush=True)

def detect_icons(slice_bgr, targets=("send","tentative"),
                 scales=(0.5, 0.6, 0.7, 0.85, 1.0, 1.15), thr_map=None):
    if not ICON_EDGES:
        _load_icon_edges()
    if thr_map is None:
        thr_map = {"send":0.55, "tentative":0.60}
    print("[icons] detect_icons start", flush=True)

    gray = cv2.cvtColor(slice_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    hits = []
    for kind in targets:
        tmpl = ICON_EDGES.get(kind)
        if tmpl is None:
            if kind == "send":
                print("[icons] 'send' template not loaded; skipping", flush=True)
            continue
        th0, tw0 = tmpl.shape[:2]
        thr = thr_map.get(kind, 0.6)
        for s in scales:
            th = max(8, int(th0*s)); tw = max(8, int(tw0*s))
            tmpl_s = cv2.resize(tmpl, (tw, th), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(edges, tmpl_s, cv2.TM_CCOEFF_NORMED)

            if kind == "send":
                try:
                    m = float(res.max())
                except Exception:
                    m = -1.0
                print(f"[icons] send scale={s:.2f} max={m:.3f}", flush=True)

            loc = np.where(res >= thr)
            for (y, x) in zip(*loc):
                score = float(res[y, x])
                hits.append({"kind":kind, "x":int(x), "y":int(y), "w":int(tw), "h":int(th), "score":score})

    # keep best only
    if not hits:
        return []
    best = max(hits, key=lambda d: d["score"])
    return [best]

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
    return {"tracking": True}

# ---- Optional: internal HDMI reader loop ----
def hdmi_loop():
    cap = cv2.VideoCapture(HDMI_DEVICE, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("[hdmi] cannot open device", HDMI_DEVICE, flush=True); return
    delay = 1.0/max(0.1, HDMI_FPS)
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.1); continue

        # Downscale and compute left slice (for icon arming)
        frame_ds = downscale_keep_long(frame, HDMI_RESIZE_LONG)
        h, w = frame_ds.shape[:2]
        left_slice = frame_ds[:, :w//2]

        # If not already tracking, try to arm via icon on the left slice (send/tentative)
        if "hdmi" not in _trackers:
            hits = detect_icons(left_slice, targets=("send","tentative"))
            if hits:
                best = hits[0]
                x, y, ww, hh = best["x"], best["y"], best["w"], best["h"]
                padw = int(ww * 1.15); padh = int(hh * 1.35)  # tighter expansion helps
                x = max(0, x - (padw - ww)//2); y = max(0, y - (padh - hh)//2)
                ww = min(left_slice.shape[1]-x, padw); hh = min(left_slice.shape[0]-y, padh)
                _trackers["hdmi"] = ROITracker(frame_ds, (x, y, ww, hh), icon_edges=ICON_EDGES.get(best["kind"]))
                print(f"[hdmi] 🎯 Icon '{best['kind']}' at ({x},{y},{ww},{hh}); tracking...", flush=True)
                time.sleep(0.5)
                # continue to next loop to start press checks
                continue

        # Run the regular frame processing (OCR + VL) in parallel
        res = process_frame("hdmi", frame)

        # If we are tracking a button, do a quick press check on the same frame
        if "hdmi" in _trackers:
            tr = _trackers["hdmi"].update_and_check(frame_ds)
            if not tr.get("ok"):
                print("[hdmi] Lost button tracking, will rearm...", flush=True)
                _trackers.pop("hdmi", None)
                time.sleep(1.0)
            elif tr.get("pressed"):
                # Confirm only if background stayed stable (avoid minimize/open)
                time.sleep(0.20)
                confirm = _trackers["hdmi"].update_and_check(frame_ds)
                confirmed = (
                    (not confirm.get("ok")) or
                    (confirm.get("ssim", 1.0) < 0.85 and confirm.get("ssim_bg", 1.0) > 0.90) or
                    (confirm.get("icon") is not None and confirm["icon"] < 0.60 and confirm.get("ssim_bg", 1.0) > 0.90) or
                    (confirm.get("pressed") is True and confirm.get("ssim_bg", 1.0) > 0.90)
                )

                print(f"[hdmi press] ssim={tr['ssim']:.2f}->{confirm.get('ssim',-1):.2f} "
                      f"bg={tr.get('ssim_bg'):.2f}->{confirm.get('ssim_bg',-1):.2f} "
                      f"dv={tr['dv']:.3f} icon={tr.get('icon')}→{confirm.get('icon')}", flush=True)

                if confirmed:
                    ha_event("vision.meeting_action", {
                        "source":"hdmi","action":"button_press","state":"pressed",
                        "metrics":{
                            "ssim":confirm.get("ssim"),
                            "ssim_bg":confirm.get("ssim_bg"),
                            "dv":confirm.get("dv"),
                            "dcontrast":confirm.get("dcontrast"),
                            "dedge":confirm.get("dedge"),
                            "icon":confirm.get("icon"),
                            "icon_drop":confirm.get("icon_drop"),
                        },
                        "bbox":confirm.get("bbox"), "ts": time.time()
                    })
                    print("[hdmi] ✅ Press confirmed", flush=True)

                    # Optional: snapshot context via OCR+VL
                    ocr_boxes = ocr_with_boxes(frame_ds)
                    crops = smart_crops(frame_ds, ocr_boxes)
                    vl_result = call_qwen_vl(frame_ds, crops)

                    result = {
                        "invite_detected": vl_result.get("invite_detected", False),
                        "button_pressed": True,
                        "vl": vl_result,
                        "anchor_button": {"bbox": confirm.get("bbox"), "keyword": "button", "text": "Tracked Button"},
                        "detection_mode": "press_triggered"
                    }

                    recent_detections.insert(0, {
                        "timestamp": time.time(),
                        "result": result,
                        "frame_b64": b64_jpg(frame_ds),
                        "button_bbox": confirm.get("bbox")
                    })
                    recent_detections[:] = recent_detections[:10]

                    # Reset tracker after press
                    _trackers.pop("hdmi", None)
                    time.sleep(2.0)
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

    Phase 1: Try cheap icon template matching on the left slice.
    Phase 2: If a candidate is found, track the region and look for a press.
    Phase 3: On press → snapshot + context/VL.
    Phase 4: If no icons, fallback to anchor OCR.
    """
    from . import anchor_detector

    # Share OCR with the anchor detector
    anchor_detector.set_shared_ocr(ocr)

    # Mode toggle
    if OCR_MODE == "full_screen":
        print("[frigate_stream] Using legacy full-screen OCR mode", flush=True)
        return frigate_stream_loop_legacy()

    print("[frigate_stream] Using press-triggered detection mode", flush=True)
    FRIGATE_API = "http://frigate:5000/api/ugreen_camera/latest.jpg"

    button_tracker = None
    tracking_source = "frigate_hdmi"

    while True:
        try:
            # -------- fetch frame --------
            resp = requests.get(FRIGATE_API, params={"_": int(time.time()*1000)}, timeout=5)  # cache-bust
            if resp.status_code != 200:
                print(f"[frigate_stream] Failed to fetch frame: {resp.status_code}", flush=True)
                time.sleep(5)
                continue

            img_array = np.frombuffer(resp.content, np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if frame is None:
                time.sleep(5)
                continue

            # Downscale for speed
            frame_ds = downscale_keep_long(frame, HDMI_RESIZE_LONG)

            # -------- if tracking, check for press --------
            if button_tracker is not None:
                # Skip frames that are basically dark (minimized/switch)
                if frame_ds.mean() < 30:
                    print("[frigate_stream] Skipping dark/minimized frame", flush=True)
                    time.sleep(0.5)
                    continue

                track_result = button_tracker.update_and_check(frame_ds)

                if not track_result.get("ok"):
                    print("[frigate_stream] Lost button tracking, rescanning...", flush=True)
                    button_tracker = None
                    time.sleep(2)
                    continue

                if track_result.get("pressed"):
                    print(f"[frigate_stream] 👆 Press detected (s={track_result['ssim']:.2f}, bg={track_result.get('ssim_bg'):.2f}, dv={track_result['dv']:.2f}, icon={track_result.get('icon')})", flush=True)
                    time.sleep(0.20)
                    confirm = button_tracker.update_and_check(frame_ds)

                    confirmed = (
                        (not confirm.get("ok")) or
                        (confirm.get("ssim", 1.0) < 0.85 and confirm.get("ssim_bg", 1.0) > 0.90) or
                        (confirm.get("icon") is not None and confirm["icon"] < 0.60 and confirm.get("ssim_bg", 1.0) > 0.90) or
                        (confirm.get("pressed") is True and confirm.get("ssim_bg", 1.0) > 0.90)
                    )

                    print(f"[press] ssim={track_result['ssim']:.2f}->{confirm.get('ssim',-1):.2f} "
                          f"bg={track_result.get('ssim_bg',-1):.2f}->{confirm.get('ssim_bg',-1):.2f} "
                          f"dv={track_result['dv']:.3f} icon={track_result.get('icon')}→{confirm.get('icon')}", flush=True)

                    if confirmed:
                        print(f"[frigate_stream] ✅ Press confirmed", flush=True)
                        tracked_bbox = track_result["bbox"]

                        ocr_boxes = ocr_with_boxes(frame_ds)
                        crops = smart_crops(frame_ds, ocr_boxes)
                        vl_result = call_qwen_vl(frame_ds, crops)

                        button_info = {"bbox": tracked_bbox, "keyword": "button", "text": "Tracked Button"}

                        ha_event("vision.meeting_action", {
                            "source": tracking_source,
                            "action": "button_press",
                            "button": button_info["keyword"],
                            "vl": vl_result,
                            "metrics": {"ssim": track_result["ssim"], "dv": track_result["dv"], "icon": track_result.get("icon"), "ssim_bg":track_result.get("ssim_bg")}
                        })

                        result = {
                            "invite_detected": vl_result.get("invite_detected", False),
                            "button_pressed": True,
                            "vl": vl_result,
                            "anchor_button": button_info,
                            "detection_mode": "press_triggered"
                        }

                        recent_detections.insert(0, {
                            "timestamp": time.time(),
                            "result": result,
                            "frame_b64": b64_jpg(frame_ds),
                            "button_bbox": tracked_bbox
                        })
                        recent_detections[:] = recent_detections[:10]

                        button_tracker = None
                        time.sleep(3)
                    else:
                        print(f"[frigate_stream] ⚠️ Looks like hover/flash or global change; keep tracking...", flush=True)
                        time.sleep(0.1)
                else:
                    time.sleep(0.1)
                continue  # next frame

            # -------- Phase 1: icon template matching on left slice --------
            h, w = frame_ds.shape[:2]
            left_slice = frame_ds[:, :w//2]  # scan 50% (button is within this)

            # --- Phase 1A: icon detection ---
            icon_hits = detect_icons(left_slice, targets=("send","tentative"))
            print("[icons] detect_icons called for send/tentative", flush=True)

            if icon_hits:
                best = icon_hits[0]
                x, y, ww, hh = best["x"], best["y"], best["w"], best["h"]
                # tighter expansion to emphasize glyph change
                padw = int(ww * 1.15); padh = int(hh * 1.35)
                x = max(0, x - (padw - ww)//2); y = max(0, y - (padh - hh)//2)
                ww = min(left_slice.shape[1]-x, padw); hh = min(left_slice.shape[0]-y, padh)

                # Start ROI tracker, pass icon edges
                button_tracker = ROITracker(frame_ds, (x, y, ww, hh), icon_edges=ICON_EDGES.get(best['kind']))
                print(f"[frigate_stream] 🎯 Icon '{best['kind']}' at ({x},{y},{ww},{hh}); tracking...", flush=True)
                time.sleep(2)
                continue  # go into tracking mode

            # -------- Phase 1 fallback: anchor OCR on left slice --------
            ocr_boxes = ocr_with_boxes(left_slice)
            if not ocr_boxes:
                time.sleep(5)
                continue

            buttons = anchor_detector.detect_buttons(left_slice, ocr_boxes=ocr_boxes)

            if buttons:
                priority_order = ["accept", "decline", "send"]
                buttons_sorted = sorted(
                    buttons,
                    key=lambda b: priority_order.index(b["keyword"]) if b["keyword"] in priority_order else 999
                )
                primary_button = buttons_sorted[0]
                x, y, bw, bh = primary_button["bbox"]

                expanded_w = int(bw * 1.6)
                expanded_h = int(bh * 1.8)
                h_frame, w_frame = frame_ds.shape[:2]
                expanded_w = min(expanded_w, w_frame - x)
                expanded_h = min(expanded_h, h_frame - y)

                button_tracker = ROITracker(frame_ds, (x, y, expanded_w, expanded_h))
                print(f"[frigate_stream] 👁️  Found '{primary_button['keyword']}' via OCR at ({x},{y}), tracking...", flush=True)
                time.sleep(2)
            else:
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
                const container = imgElement.parentElement;
                const existingCanvas = container.querySelector('canvas');
                if (existingCanvas) existingCanvas.remove();
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                canvas.width = imgElement.naturalWidth;
                canvas.height = imgElement.naturalHeight;
                canvas.style.width = '100%';
                canvas.style.height = '100%';
                canvas.style.position = 'absolute';
                canvas.style.top = '0';
                canvas.style.left = '0';
                canvas.style.pointerEvents = 'none';
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

                        const imgId = 'img_' + d.timestamp;

                        return `
                            <div class="detection">
                                <div class="timestamp">${new Date(d.timestamp * 1000).toLocaleString()}</div>
                                ${buttonInfo}
                                <div class="image-container" style="position: relative; display: inline-block;">
                                    <img id="${imgId}" src="data:image/jpeg;base64,${d.frame_b64}"
                                         style="display: block; max-width: 100%; height: auto;"
                                         onload='drawBoundingBoxes(this, ${JSON.stringify(d.button_bbox)})'>
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

# Start Frigate stream processor
threading.Thread(target=frigate_stream_loop, daemon=True).start()

if HDMI_ENABLED:
    threading.Thread(target=hdmi_loop, daemon=True).start()
