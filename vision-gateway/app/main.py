import os, re, time, threading, base64
from typing import List, Dict, Any, Tuple

import numpy as np
import cv2
import requests
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
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

HDMI_ENABLED = os.getenv("HDMI_ENABLED", "false").lower() == "true"
HDMI_DEVICE  = os.getenv("HDMI_DEVICE", "/dev/video0")

# Native capture size (what your dongle actually supports)
CAP_WIDTH   = int(os.getenv("HDMI_WIDTH", "1920"))
CAP_HEIGHT  = int(os.getenv("HDMI_HEIGHT", "1080"))
CAP_FPS_REQ = int(os.getenv("HDMI_CAP_FPS", "10"))

# YUYV by default; set HDMI_FORCE_MJPG=true to start in MJPG
FORCE_MJPG = os.getenv("HDMI_FORCE_MJPG", "false").lower() == "true"

# Button fixed region (NATIVE coordinates)
BUTTON_COORDS = os.getenv("BUTTON_COORDS", "45,350,90,114")  # x,y,w,h

# Thresholds
BUTTON_THRESH    = float(os.getenv("BUTTON_THRESH", "0.40"))  # arming on idle "send"
PRESSED_THRESH   = float(os.getenv("PRESSED_THRESH", "0.55")) # absolute backstop for pressed
DISAPPEAR_THRESH = float(os.getenv("DISAPPEAR_THRESH", "0.35"))
PRESS_MARGIN     = float(os.getenv("PRESS_MARGIN", "0.04"))   # pressed - idle >= margin
MIN_PRESSED      = float(os.getenv("MIN_PRESSED", "0.50"))    # ignore very low pressed

# Debounce / timing
DISAPPEAR_FRAMES = int(os.getenv("DISAPPEAR_FRAMES", "3"))    # frames to confirm end
PRESS_TIMEOUT_S  = float(os.getenv("PRESS_TIMEOUT_S", "3.0")) # max time in PRESS
REARM_COOLDOWN   = float(os.getenv("REARM_COOLDOWN", "1.5"))  # after cycle finishes
MATCH_EVERY_N    = int(os.getenv("MATCH_EVERY_N", "3"))       # run matcher every N frames

# Downscale for the Qwen snapshot (only for the single post-press screenshot)
HDMI_RESIZE_LONG = int(os.getenv("HDMI_RESIZE_LONG", "1280"))

# ---------------------- App ----------------------
app = FastAPI(title="Vision Gateway (Native ROI + Masked Matching)")

def b64_jpg(img: np.ndarray, q: int = 90) -> str:
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    return base64.b64encode(buf).decode("ascii") if ok else ""

def ha_event(event_type: str, data: Dict[str,any]):
    if not HA_BASE or not HA_TOKEN:
        return
    try:
        requests.post(
            f"{HA_BASE}/api/events/{event_type}",
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type":"application/json"},
            json=data, timeout=3.0
        )
    except Exception:
        pass

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

def call_qwen_vl(full_img: np.ndarray) -> Dict[str,any]:
    """Qwen only (no OCR); send just the full frame."""
    prompt = (
      "You are a UI vision agent. From this image, determine if there is a meeting invite/join dialog. "
      "Extract: app (Teams/Zoom/Meet/Unknown), invite_detected (true/false), title, attendees, "
      "start_iso, end_iso if present, buttons (array), and action_state (one of: pending/accepted/declined/joined/none). "
      "Return strict minified JSON with keys: app, invite_detected, title, attendees, start_iso, end_iso, buttons, action_state, confidence."
    )
    images = [b64_jpg(full_img, 85)]
    try:
        r = requests.post(f"{OLLAMA_VISION_BASE}/api/generate",
                          json={"model": OLLAMA_VISION_MODEL, "prompt": prompt, "images": images, "stream": False},
                          timeout=30)
        r.raise_for_status()
        txt = r.json().get("response","").strip()
        import json
        m = re.search(r"\{.*\}", txt, re.S)
        return json.loads(m.group(0)) if m else {"app":"Unknown","invite_detected":False,"title":"","attendees":"","start_iso":"","end_iso":"","buttons":[],"action_state":"none","confidence":0.0}
    except Exception:
        return {"app":"Unknown","invite_detected":False,"title":"","attendees":"","start_iso":"","end_iso":"","buttons":[],"action_state":"none","confidence":0.0}

# ---------------------- Templates (grayscale + mask) ----------------------
ICON_PATHS = {
    "send":          "/app/assets/send.png",
    "send_pressed":  "/app/assets/send_pressed.PNG",
}
ICON_GRAY: Dict[str, np.ndarray] = {}
ICON_MASK: Dict[str, np.ndarray] = {}

def _prep_gray(img: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = cv2.GaussianBlur(g, (3,3), 0)  # reduce aliasing jitter
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    g = clahe.apply(g)
    return g

def _load_icon_gray():
    ICON_GRAY.clear(); ICON_MASK.clear()
    for k, p in ICON_PATHS.items():
        if not os.path.exists(p): 
            continue
        g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if g is None: 
            continue
        gg = _prep_gray(g)

        # Build a mask that isolates the arrow strokes (ignore background fill)
        edges = cv2.Canny(g, 60, 140)
        edges = cv2.dilate(edges, np.ones((3,3), np.uint8), iterations=1)
        _, mask = cv2.threshold(edges, 1, 255, cv2.THRESH_BINARY)

        ICON_GRAY[k] = gg
        ICON_MASK[k] = mask
    print(f"[icons] loaded: {list(ICON_GRAY.keys())}", flush=True)

def _match_max(gray_roi: np.ndarray, tmpl_gray: np.ndarray) -> float:
    """Adaptive 5-scale matcher centered on fitting the template to ROI."""
    if tmpl_gray is None or gray_roi.size == 0:
        return -1.0
    best = -1.0
    th0, tw0 = tmpl_gray.shape[:2]
    if th0 == 0 or tw0 == 0:
        return -1.0
    gh, gw = gray_roi.shape[:2]
    s0 = min(gh / max(1, th0), gw / max(1, tw0))
    scales = [s0*0.85, s0*0.93, s0, s0*1.07, s0*1.15]
    for s in scales:
        th = max(6, int(th0*s)); tw = max(6, int(tw0*s))
        if gh < th or gw < tw:
            continue
        tmpl_s = cv2.resize(tmpl_gray, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(gray_roi, tmpl_s, cv2.TM_CCOEFF_NORMED)
        if res.size:
            val = float(res.max())
            if val > best: best = val
    return best

def _match_max_masked(gray_roi: np.ndarray, tmpl_gray: np.ndarray, tmpl_mask: np.ndarray) -> float:
    """
    Masked matching: focus on the arrow strokes only (ignores background).
    Uses TM_CCORR_NORMED which supports mask.
    """
    if tmpl_gray is None or tmpl_mask is None or gray_roi.size == 0:
        return -1.0
    best = -1.0
    th0, tw0 = tmpl_gray.shape[:2]
    if th0 == 0 or tw0 == 0:
        return -1.0
    gh, gw = gray_roi.shape[:2]
    # Native scale should be close; small jitter around 1.0
    s0 = min(gh / max(1, th0), gw / max(1, tw0))
    scales = [s0*0.90, s0, s0*1.10]
    for s in scales:
        th = max(6, int(th0*s)); tw = max(6, int(tw0*s))
        if gh < th or gw < tw:
            continue
        t_s = cv2.resize(tmpl_gray, (tw, th), interpolation=cv2.INTER_AREA)
        m_s = cv2.resize(tmpl_mask, (tw, th), interpolation=cv2.INTER_NEAREST).astype(np.uint8)
        # Ensure mask is binary 0/255
        _, m_s = cv2.threshold(m_s, 1, 255, cv2.THRESH_BINARY)
        res = cv2.matchTemplate(gray_roi, t_s, cv2.TM_CCORR_NORMED, mask=m_s)
        if res.size:
            val = float(res.max())
            if val > best: best = val
    return best

def _open_capture(dev: str, width: int, height: int, fps: int, prefer_mjpg: bool = False):
    cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
    if not cap.isOpened():
        return None
    if prefer_mjpg:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS,          fps)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
    except Exception:
        pass
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fmt = "".join([chr((fourcc >> 8*i) & 0xFF) for i in range(4)])
    print(f"[hdmi] requested {width}x{height}@{fps} {'MJPG' if prefer_mjpg else 'raw'}; "
          f"got {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}@{cap.get(cv2.CAP_PROP_FPS):.0f} {fmt}",
          flush=True)
    return cap

def _read_frame_robust(cap, retries: int = 3):
    for _ in range(retries):
        try:
            ok, frame = cap.read()
            if ok and frame is not None:
                return True, frame
        except cv2.error:
            time.sleep(0.02)
            continue
        time.sleep(0.01)
    return False, None

def _grab_fullres_snapshot(cap, prefer_mjpg: bool, nat_w: int, nat_h: int, fps: int, retries: int = 3):
    """Temporarily set full-res, grab one frame, then restore settings."""
    cur_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    cur_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cur_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cur_fps = int(cap.get(cv2.CAP_PROP_FPS))

    if prefer_mjpg:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  nat_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, nat_h)
    cap.set(cv2.CAP_PROP_FPS,          fps)

    ok, full = _read_frame_robust(cap, retries=retries)

    # restore previous scan settings
    if not FORCE_MJPG:
        cap.set(cv2.CAP_PROP_FOURCC, cur_fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  cur_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cur_h)
    cap.set(cv2.CAP_PROP_FPS,          cur_fps)

    return full if ok else None

def _roi_variance(g: np.ndarray) -> float:
    return float(np.var(g)) if g.size else 0.0

FLAT_VAR = float(os.getenv("FLAT_VAR", "20.0"))

# ---------------------- Debug storage ----------------------
recent_detections: List[Dict[str,any]] = []  # last 10

# ---------------------- HDMI loop (native ROI, no downscale) ----------------------
def hdmi_loop():
    prefer_mjpg = FORCE_MJPG
    cap = _open_capture(HDMI_DEVICE, CAP_WIDTH, CAP_HEIGHT, CAP_FPS_REQ, prefer_mjpg=prefer_mjpg)
    if cap is None:
        print(f"[hdmi] cannot open device {HDMI_DEVICE}", flush=True)
        return

    # Parse button coords (native)
    try:
        bx, by, bw, bh = map(int, BUTTON_COORDS.split(","))
    except Exception:
        print(f"[hdmi] Invalid BUTTON_COORDS '{BUTTON_COORDS}', expected 'x,y,w,h'. Exiting.", flush=True)
        return
    print(f"[hdmi] Using fixed region BUTTON_COORDS = (x={bx}, y={by}, w={bw}, h={bh})", flush=True)

    _load_icon_gray()
    if "send" not in ICON_GRAY or "send_pressed" not in ICON_GRAY:
        print("[hdmi] Missing /app/assets/send.png or /app/assets/send_pressed.PNG", flush=True)
    send_t   = ICON_GRAY.get("send")
    send_m   = ICON_MASK.get("send")
    press_t  = ICON_GRAY.get("send_pressed")
    press_m  = ICON_MASK.get("send_pressed")

    delay = 1.0 / max(0.1, CAP_FPS_REQ)
    state = "SCANNING"

    # Debouncers / timers
    seen_send = 0
    seen_press = 0
    seen_disappear = 0
    no_button = 0
    pressed_ts = 0.0
    frame_i = 0

    print("[hdmi] State: SCANNING (native-ROI scan, full-res snapshot on press; masked matching)", flush=True)

    consecutive_failures = 0
    last_reopen = 0.0

    while True:
        ok, frame = _read_frame_robust(cap, retries=3)
        if not ok:
            consecutive_failures += 1
            if consecutive_failures >= 5 and (time.time() - last_reopen) > 1.0:
                print("[hdmi] ⚠️ read() failing; reopening capture...", flush=True)
                try: cap.release()
                except Exception: pass
                if prefer_mjpg and consecutive_failures >= 10:
                    print("[hdmi] 🔁 switching to YUYV (more robust) due to repeated MJPG errors", flush=True)
                    prefer_mjpg = False
                cap = _open_capture(HDMI_DEVICE, CAP_WIDTH, CAP_HEIGHT, CAP_FPS_REQ, prefer_mjpg=prefer_mjpg)
                last_reopen = time.time()
                consecutive_failures = 0
            time.sleep(0.02)
            continue

        consecutive_failures = 0
        frame_i += 1

        # --- Native ROI (pad generously to absorb small drift) ---
        x0, y0, w0, h0 = bx, by, bw, bh
        pad_x = int(w0 * 0.60)
        pad_y = int(h0 * 0.60)
        x0p = max(0, x0 - pad_x)
        y0p = max(0, y0 - pad_y)
        x1p = min(frame.shape[1], x0 + w0 + pad_x)
        y1p = min(frame.shape[0], y0 + h0 + pad_y)
        roi = frame[y0p:y1p, x0p:x1p]
        if roi.size == 0:
            time.sleep(delay); continue
        roi_gray = _prep_gray(roi)

        # Only run matchers every N frames to keep CPU low
        should_match = (frame_i % MATCH_EVERY_N == 0)

        if state == "SCANNING":
            if not should_match or send_t is None:
                time.sleep(delay); continue

            score_g = _match_max(roi_gray, send_t)
            score_m = _match_max_masked(roi_gray, send_t, send_m)
            score   = max(score_g, score_m)

            if frame_i % (MATCH_EVERY_N*10) == 0:
                print(f"[hdmi][scan] roi={roi_gray.shape[::-1]} send:g={score_g:.3f} m={score_m:.3f} -> {score:.3f} thr={BUTTON_THRESH}", flush=True)

            weak = (score < (BUTTON_THRESH - 0.08))
            no_button = (no_button + 1) if weak else 0

            if score >= BUTTON_THRESH:
                seen_send += 1
            else:
                seen_send = 0

            if seen_send >= 2:
                state = "ARMED"
                seen_press = 0
                print(f"[hdmi] ✅ ARMED @ fixed region (native {bx},{by},{bw},{bh}) score={score:.3f}", flush=True)

        elif state == "ARMED":
            if not should_match or press_t is None:
                time.sleep(delay); continue

            ps_g = _match_max(roi_gray, press_t)
            ps_m = _match_max_masked(roi_gray, press_t, press_m)
            pscore = max(ps_g, ps_m)

            ss_g = _match_max(roi_gray, send_t) if send_t is not None else -1.0
            ss_m = _match_max_masked(roi_gray, send_t, send_m) if send_t is not None else -1.0
            sscore = max(ss_g, ss_m)

            # Auto-dearm if both weak for a while (window hidden)
            weak_both = (pscore < (PRESSED_THRESH - 0.10)) and (sscore < (BUTTON_THRESH - 0.10))
            no_button = (no_button + 1) if weak_both else 0
            if no_button >= 15:
                print("[hdmi] ↩︎ Button gone (window minimized/closed) — de-arming", flush=True)
                state = "SCANNING"
                seen_send = seen_press = seen_disappear = 0
                no_button = 0

            # Relative press condition (or absolute backstop)
            looks_pressed_abs = (pscore >= PRESSED_THRESH)
            pressed_wins      = (pscore >= MIN_PRESSED) and (pscore - sscore >= PRESS_MARGIN)
            if looks_pressed_abs or pressed_wins:
                seen_press += 1
            else:
                seen_press = 0

            if frame_i % (MATCH_EVERY_N*10) == 0:
                print(f"[hdmi][armed] p(g={ps_g:.3f},m={ps_m:.3f})={pscore:.3f}  "
                      f"s(g={ss_g:.3f},m={ss_m:.3f})={sscore:.3f}  Δ={pscore-sscore:.3f}", flush=True)

            if seen_press >= 2:
                # Take a full-res snapshot, then go to PRESS
                full = _grab_fullres_snapshot(cap, prefer_mjpg=prefer_mjpg,
                                              nat_w=CAP_WIDTH, nat_h=CAP_HEIGHT, fps=CAP_FPS_REQ)
                screenshot = full if full is not None else frame.copy()
                state = "PRESS"
                pressed_ts = time.time()
                seen_disappear = 0
                print(f"[hdmi] 🖱️ PRESS p={pscore:.3f} s={sscore:.3f} Δ={pscore-sscore:.3f}", flush=True)

                # Qwen-only context (no OCR)
                shot_ds = downscale_keep_long(screenshot, HDMI_RESIZE_LONG)
                def _process_context(img):
                    try:
                        vl = call_qwen_vl(img)
                        ha_event("vision.meeting_action", {
                            "source": "hdmi",
                            "action": "button_press_confirmed",
                            "vl": vl,
                            "ts": time.time()
                        })
                        recent_detections.insert(0, {
                            "timestamp": time.time(),
                            "result": {
                                "invite_detected": vl.get("invite_detected", False),
                                "button_pressed": True,
                                "vl": vl,
                                "detection_mode": "fixed_region_templates_native_roi"
                            },
                            "frame_b64": b64_jpg(img, 85),
                            "button_bbox": [bx, by, bw, bh]
                        })
                        del recent_detections[10:]
                        print("[hdmi] 📅 Context processed (Qwen only) & event sent", flush=True)
                    except Exception as e:
                        print(f"[hdmi] Context error: {e}", flush=True)
                threading.Thread(target=_process_context, args=(shot_ds,), daemon=True).start()

        elif state == "PRESS":
            # Always evaluate in PRESS; no frame skipping
            sscore = max(
                _match_max(roi_gray, send_t)  if send_t  is not None else -1.0,
                _match_max_masked(roi_gray, send_t, send_m) if send_t is not None else -1.0
            )
            pscore = max(
                _match_max(roi_gray, press_t) if press_t is not None else -1.0,
                _match_max_masked(roi_gray, press_t, press_m) if press_t is not None else -1.0
            )

            flat    = (_roi_variance(roi_gray) < FLAT_VAR)
            timeout = (time.time() - pressed_ts) > PRESS_TIMEOUT_S

            cond_disappear = (send_t is None) or (sscore < DISAPPEAR_THRESH)
            cond_unpress   = (press_t is None) or (pscore < (PRESSED_THRESH - 0.10))

            if cond_disappear or cond_unpress or flat or timeout:
                seen_disappear += 1
            else:
                seen_disappear = 0

            if frame_i % 15 == 0:
                print(f"[hdmi][press] s={sscore:.3f} p={pscore:.3f} flat={flat} "
                      f"t+={time.time()-pressed_ts:.1f}s count={seen_disappear}", flush=True)

            if seen_disappear >= DISAPPEAR_FRAMES:
                state = "SCANNING"
                seen_send = seen_press = seen_disappear = no_button = 0
                print(f"[hdmi] ✅ Cycle complete; re-arming", flush=True)
                time.sleep(REARM_COOLDOWN)

        time.sleep(delay)

# ---------------------- HTTP API ----------------------
class Ingest(BaseModel):
    source: str

@app.post("/ingest_frame")
async def ingest_frame(source: str = Form(...), file: UploadFile = File(...)):
    img_bytes = await file.read()
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    return {"ok": True, "shape": img.shape if img is not None else None}

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/api/detections")
def get_recent_detections():
    return recent_detections

@app.get("/debug")
def debug_page():
    html = """
    <!doctype html><html><head>
      <meta http-equiv="refresh" content="5">
      <title>Vision Gateway Debug</title>
      <style>
        body{font-family:monospace;background:#111;color:#0f0;padding:20px}
        .head{border-bottom:1px solid #0f0;margin-bottom:10px;padding-bottom:6px}
        .card{border:1px solid #0f0;padding:10px;margin:14px 0;background:#000}
        img{max-width:640px;border:1px solid #0f0}
        .ts{color:#0ff}
      </style>
    </head><body>
      <div class="head"><h2>Vision Gateway – Native ROI + Masked Matching</h2>
        <p>Scans a tiny native corner only; snapshots full-res once on press. Qwen-only post-press.</p>
      </div>
      <div id="list"></div>
      <script>
        fetch('/api/detections').then(r=>r.json()).then(arr=>{
          if(!arr.length){document.getElementById('list').innerHTML='<p>No detections yet…</p>';return;}
          document.getElementById('list').innerHTML = arr.map(d=>{
            const vl = d.result?.vl || {};
            return `
              <div class="card">
                <div class="ts">${new Date(d.timestamp*1000).toLocaleString()}</div>
                <div>Invite: ${vl.invite_detected ? 'true' : 'false'}</div>
                ${vl.title ? `<div>Title: ${vl.title}</div>` : ``}
                ${vl.start_iso ? `<div>Start: ${vl.start_iso}</div>` : ``}
                ${vl.end_iso ? `<div>End: ${vl.end_iso}</div>` : ``}
                ${vl.app ? `<div>App: ${vl.app}</div>` : ``}
                <div><img src="data:image/jpeg;base64,${d.frame_b64}"/></div>
              </div>`;
          }).join('');
        });
      </script>
    </body></html>
    """
    return HTMLResponse(html)

# ---------------------- Startup ----------------------
if HDMI_ENABLED:
    threading.Thread(target=hdmi_loop, daemon=True).start()
