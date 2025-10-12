import os, re, time, threading, base64
from collections import deque
from typing import List, Dict, Any, Tuple
from contextlib import asynccontextmanager

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

# K80 GPU preprocessing (Phase 2)
K80_ENABLED = os.getenv("K80_ENABLED", "false").lower() == "true"
K80_DEVICE = os.getenv("K80_DEVICE", "cuda:2")
K80_BOX_THRESHOLD = float(os.getenv("K80_BOX_THRESHOLD", "0.35"))
K80_TEXT_THRESHOLD = float(os.getenv("K80_TEXT_THRESHOLD", "0.25"))
K80_SCENE_CHANGE_THRESHOLD = float(os.getenv("K80_SCENE_CHANGE_THRESHOLD", "0.3"))

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
PRESS_DELTA      = float(os.getenv("PRESS_DELTA", "0.07"))    # how much better "press" must be than "send"

# Once pressed, require scores to fall this far below PRESSED_THRESH before releasing
PRESS_RELEASE = max(0.0, PRESSED_THRESH - 0.18)

# Debounce / timing
DISAPPEAR_FRAMES = int(os.getenv("DISAPPEAR_FRAMES", "3"))    # frames to confirm end
PRESS_TIMEOUT_S  = float(os.getenv("PRESS_TIMEOUT_S", "3.0")) # max time in PRESS
REARM_COOLDOWN   = float(os.getenv("REARM_COOLDOWN", "1.5"))  # after cycle finishes
MATCH_EVERY_N    = int(os.getenv("MATCH_EVERY_N", "3"))       # run matcher every N frames

# Downscale for the Qwen snapshot (only for the single post-press screenshot)
HDMI_RESIZE_LONG = int(os.getenv("HDMI_RESIZE_LONG", "1280"))

# ---------------------- App ----------------------
app = FastAPI(title="Vision Gateway (Native ROI + Masked Matching)")

@app.on_event("startup")
async def startup_event():
    """Start HDMI capture thread on startup"""
    # Force rebuild
    if HDMI_ENABLED:
        print("Starting HDMI capture loop in background thread...", flush=True)
        hdmi_thread = threading.Thread(target=hdmi_loop, daemon=True)
        hdmi_thread.start()
    else:
        print("HDMI capture is disabled.", flush=True)

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
    except Exception as e:
        print(f"HA event error: {e}", flush=True)

# ---------------------- Globals ----------------------
# Recent detection cache
recent_detections: List[Dict[str,Any]] = []

# Icon templates (loaded at runtime)
ICON_GRAY: Dict[str, np.ndarray] = {}
ICON_MASK: Dict[str, np.ndarray] = {}

# Variance threshold for detecting a "flat" (blank) screen
FLAT_VAR = float(os.getenv("FLAT_VAR", "100.0"))

# ---------------------- Image Utils ----------------------
def _prep_gray(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 3 and img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img

def _roi_variance(img_gray: np.ndarray) -> float:
    return np.var(img_gray)

def _load_icon_gray():
    global ICON_GRAY, ICON_MASK
    if ICON_GRAY: return
    for name in ["send", "send_pressed"]:
        path = f"/app/assets/{name}.png"
        if not os.path.exists(path): continue
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None: continue
        if len(img.shape) == 3 and img.shape[2] == 4:
            b, g, r, a = cv2.split(img)
            # Use alpha as mask
            ICON_MASK[name] = a
            # Create grayscale from BGR
            ICON_GRAY[name] = cv2.cvtColor(cv2.merge((b,g,r)), cv2.COLOR_BGR2GRAY)
        else:
            ICON_GRAY[name] = _prep_gray(img)
    print(f"Loaded icons: {list(ICON_GRAY.keys())}", flush=True)

def _match_max(scene: np.ndarray, template: np.ndarray) -> float:
    if scene is None or template is None or scene.size==0 or template.size==0: return -1.0
    if template.shape[0] > scene.shape[0] or template.shape[1] > scene.shape[1]: return -1.0
    res = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return float(max_val)

def _match_max_masked(scene: np.ndarray, template: np.ndarray, mask: np.ndarray) -> float:
    if scene is None or template is None or mask is None: return -1.0
    if scene.size==0 or template.size==0 or mask.size==0: return -1.0
    if template.shape[0] > scene.shape[0] or template.shape[1] > scene.shape[1]: return -1.0
    res = cv2.matchTemplate(scene, template, cv2.TM_CCORR_NORMED, mask=mask)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return float(max_val)

def downscale_keep_long(img: np.ndarray, long_edge: int) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= long_edge:
        return img
    if h > w:
        new_h = long_edge
        new_w = int(w * (long_edge / h))
    else:
        new_w = long_edge
        new_h = int(h * (long_edge / w))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

# ---------------------- Qwen-VL Call ----------------------
class QwenResponse(BaseModel):
    invite_detected: bool = False
    decision: str = ""
    reasoning: str = ""

def call_qwen_vl(img: np.ndarray) -> Dict[str, Any]:
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
                    "You are an expert at parsing meeting invitation popups on a computer screen. "
                    "Analyze the image and determine if it shows a meeting invitation. "
                    "If it does, what is the required decision (e.g., 'Join', 'Accept')? "
                    "Respond with JSON."
                ),
                "system": (
                    "You must respond in JSON format with three fields: "
                    '`"invite_detected": bool`, `"decision": "brief action string"`, '
                    '`"reasoning": "your analysis"`. Do not include code fences.'
                )
            }
        )
        res.raise_for_status()
        body = res.json()
        return QwenResponse.model_validate_json(body.get("response", "{}")).model_dump()
    except Exception as e:
        print(f"Qwen-VL error: {e}", flush=True)
        return {"error": str(e)}

# ---------------------- HDMI Capture Loop ----------------------
def _open_capture(dev: str, w: int, h: int, fps: int, prefer_mjpg: bool = False):
    try:
        cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
        if not cap.isOpened(): return None
        if prefer_mjpg:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        else:
            # YUYV is often more stable
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_FPS, fps)
        # Verify settings
        actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
        print(f"[hdmi] Opened {dev} @ {actual_w}x{actual_h} {actual_fps}fps, Codec:{codec}", flush=True)
        return cap
    except Exception as e:
        print(f"[hdmi] Error opening {dev}: {e}", flush=True)
        return None

def _read_frame_robust(cap: cv2.VideoCapture, retries: int = 2) -> Tuple[bool, np.ndarray]:
    for _ in range(retries):
        ok, frame = cap.read()
        if ok: return True, frame
        time.sleep(0.01)
    return False, np.array([])

def _grab_fullres_snapshot(cap: cv2.VideoCapture, prefer_mjpg: bool, nat_w: int, nat_h: int, fps: int):
    # Temporarily reopen at full-res to get a sharp image
    print("[hdmi] Grabbing full-res snapshot...", flush=True)
    temp_cap = None
    try:
        cap.release()
        temp_cap = _open_capture(HDMI_DEVICE, nat_w, nat_h, fps, prefer_mjpg=prefer_mjpg)
        if temp_cap is None: return None
        ok, frame = _read_frame_robust(temp_cap, retries=5)
        return frame if ok else None
    finally:
        if temp_cap: temp_cap.release()
        # Important: Reopen original capture to continue loop
        cap.open(HDMI_DEVICE, cv2.CAP_V4L2)
        if prefer_mjpg:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        else:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAP_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAP_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, CAP_FPS_REQ)
        print("[hdmi] Original capture re-established.", flush=True)

def hdmi_loop():
    if not HDMI_ENABLED:
        print("[hdmi] Not enabled, skipping.", flush=True)
        return

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

    # Initialize K80 preprocessor if enabled
    k80_preprocessor = None
    k80_scene_tracker = None
    k80_enabled = K80_ENABLED  # Local copy to avoid scope issues
    if k80_enabled:
        try:
            from app.k80_preprocessor import K80Preprocessor, SceneTracker
            print(f"[hdmi] Initializing K80 preprocessor on {K80_DEVICE}...", flush=True)
            k80_preprocessor = K80Preprocessor(
                device=K80_DEVICE,
                box_threshold=K80_BOX_THRESHOLD,
                text_threshold=K80_TEXT_THRESHOLD,
            )
            k80_scene_tracker = SceneTracker(change_threshold=K80_SCENE_CHANGE_THRESHOLD)
            print("[hdmi] K80 preprocessor initialized successfully!", flush=True)
        except Exception as e:
            print(f"[hdmi] WARNING: K80 preprocessor failed to initialize: {e}", flush=True)
            print("[hdmi] Falling back to template matching only", flush=True)
            k80_enabled = False

    delay = 1.0 / max(0.1, CAP_FPS_REQ)
    state = "SCANNING"

    # Debouncers / timers
    seen_send = 0
    seen_disappear = 0
    no_button = 0
    pressed_ts = 0.0
    frame_i = 0

    # Running score history (for temporal median filtering)
    press_scores: deque = deque(maxlen=5)
    send_scores: deque = deque(maxlen=5)

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

        # Store latest frame for API access (Computer Control Agent)
        global latest_frames
        latest_frames["hdmi"] = {
            "image_b64": b64_jpg(frame),
            "timestamp": time.time()
        }

        # K80 continuous detection (Phase 2)
        if k80_preprocessor is not None and frame_i % MATCH_EVERY_N == 0:
            try:
                detections = k80_preprocessor.detect_elements(
                    frame,
                    prompts=["button", "send button", "accept button", "join button", "dialog box"]
                )
                detection_summary = k80_preprocessor.get_detection_summary(detections)

                # Check for scene changes
                if k80_scene_tracker.has_changed(detection_summary, k80_preprocessor):
                    # Scene changed - call Qwen for deep analysis
                    print(f"[k80] Scene change detected, triggering Qwen analysis...", flush=True)
                    shot_ds = downscale_keep_long(frame, HDMI_RESIZE_LONG)

                    def _k80_qwen_analysis(img, dets):
                        try:
                            vl = call_qwen_vl(img)
                            ha_event("vision.k80_scene_change", {
                                "source": "hdmi_k80",
                                "detections": [{"label": d.label, "bbox": d.bbox, "confidence": d.confidence} for d in dets],
                                "vl": vl,
                                "ts": time.time()
                            })
                            recent_detections.insert(0, {
                                "timestamp": time.time(),
                                "result": {
                                    "k80_detections": [{"label": d.label, "bbox": d.bbox, "confidence": d.confidence} for d in dets],
                                    "vl": vl,
                                    "detection_mode": "k80_groundingdino"
                                },
                                "frame_b64": b64_jpg(img, 85),
                            })
                            del recent_detections[10:]
                        except Exception as e:
                            print(f"[k80] Qwen analysis error: {e}", flush=True)

                    threading.Thread(target=_k80_qwen_analysis, args=(shot_ds, detections), daemon=True).start()

            except Exception as e:
                print(f"[k80] Detection error: {e}", flush=True)

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

        if state == "SCANNING":
            if (frame_i % MATCH_EVERY_N != 0) or send_t is None:
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
                press_scores.clear(); send_scores.clear()
                print(f"[hdmi] ✅ ARMED @ fixed region (native {bx},{by},{bw},{bh}) score={score:.3f}", flush=True)

        elif state == "ARMED":
            ps_g = _match_max(roi_gray, press_t)
            ps_m = _match_max_masked(roi_gray, press_t, press_m)
            pscore = max(ps_g, ps_m)

            ss_g = _match_max(roi_gray, send_t) if send_t is not None else -1.0
            ss_m = _match_max_masked(roi_gray, send_t, send_m) if send_t is not None else -1.0
            sscore = max(ss_g, ss_m)

            press_scores.append(pscore)
            send_scores.append(sscore)

            press_med = float(np.median(list(press_scores))) if press_scores else pscore
            send_med = float(np.median(list(send_scores))) if send_scores else sscore
            inst_delta = (pscore - sscore) if send_t is not None else float("inf")

            # Auto-dearm if both weak for a while (window hidden)
            weak_both = (press_med < (PRESSED_THRESH - 0.10)) and (send_med < (BUTTON_THRESH - 0.10))
            no_button = (no_button + 1) if weak_both else 0
            if no_button >= 15:
                print("[hdmi] ↩︎ Button gone (window minimized/closed) — de-arming", flush=True)
                state = "SCANNING"
                seen_send = seen_disappear = 0
                no_button = 0
                press_scores.clear(); send_scores.clear()
                time.sleep(delay)
                continue

            delta = press_med - send_med if send_t is not None else float("inf")
            looks_pressed = (
                (press_med >= PRESSED_THRESH)
                and (delta >= PRESS_DELTA)
                and (inst_delta >= max(0.0, PRESS_DELTA * 0.6))
            )

            if frame_i % 20 == 0:
                print(f"[hdmi][armed] med_p={press_med:.3f} med_s={send_med:.3f} "
                      f"p(g={ps_g:.3f},m={ps_m:.3f})={pscore:.3f}  "
                      f"s(g={ss_g:.3f},m={ss_m:.3f})={sscore:.3f}", flush=True)

            if looks_pressed:
                # Take a full-res snapshot, then go to PRESS
                full = _grab_fullres_snapshot(cap, prefer_mjpg=prefer_mjpg,
                                              nat_w=CAP_WIDTH, nat_h=CAP_HEIGHT, fps=CAP_FPS_REQ)
                screenshot = full if full is not None else frame.copy()
                state = "PRESS"
                pressed_ts = time.time()
                seen_disappear = 0
                # Keep the running history warm for PRESS state
                press_scores.append(pscore)
                send_scores.append(sscore)
                print(
                    f"[hdmi] 🖱️ PRESS p={pscore:.3f} s={sscore:.3f} Δ={pscore-sscore:.3f} "
                    f"medΔ={delta:.3f}",
                    flush=True,
                )

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

            press_scores.append(pscore)
            send_scores.append(sscore)
            press_med = float(np.median(list(press_scores))) if press_scores else pscore
            send_med = float(np.median(list(send_scores))) if send_scores else sscore
            inst_delta = (pscore - sscore) if send_t is not None else float("inf")

            flat    = (_roi_variance(roi_gray) < FLAT_VAR)
            timeout = (time.time() - pressed_ts) > PRESS_TIMEOUT_S

            cond_disappear = (send_t is None) or (send_med < DISAPPEAR_THRESH)
            delta = press_med - send_med if send_t is not None else float("inf")
            cond_unpress   = (
                (press_t is None)
                or (press_med <= PRESS_RELEASE)
                or (delta <= (PRESS_DELTA * 0.5))
                or (inst_delta <= (PRESS_DELTA * 0.25))
            )

            if cond_disappear or cond_unpress or flat or timeout:
                seen_disappear += 1
            else:
                seen_disappear = 0

            if frame_i % 15 == 0:
                print(f"[hdmi][press] s={sscore:.3f} p={pscore:.3f} flat={flat} "
                      f"t+={time.time()-pressed_ts:.1f}s count={seen_disappear}", flush=True)

            if seen_disappear >= DISAPPEAR_FRAMES:
                state = "SCANNING"
                seen_send = seen_disappear = no_button = 0
                press_scores.clear(); send_scores.clear()
                print(f"[hdmi] ✅ Cycle complete; re-arming", flush=True)
                time.sleep(REARM_COOLDOWN)

        time.sleep(delay)

# ---------------------- HTTP API ----------------------
# Store latest frames per source for Computer Control Agent access
latest_frames: Dict[str, Dict[str, Any]] = {}  # source -> {"image_b64": str, "timestamp": float}

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

# Store latest frames per source
latest_frames: Dict[str, Dict[str, Any]] = {}  # source -> {"image_b64": str, "timestamp": float}

@app.get("/api/latest_frame/{source}")
def get_latest_frame(source: str):
    """
    Get the latest frame from a specific source
    
    Args:
        source: Source name (e.g., "frigate_hdmi", "hdmi", "local")
    
    Returns:
        JSON with base64-encoded image and timestamp
    """
    if source not in latest_frames:
        return {"error": f"No frames available for source '{source}'"}
    
    frame_data = latest_frames[source]
    return {
        "image": frame_data["image_b64"],
        "timestamp": frame_data["timestamp"],
        "source": source
    }

from fastapi.responses import HTMLResponse

@app.get("/debug")
def debug_page():
    global recent_detections
    if not recent_detections:
        return HTMLResponse("<html><body>No detections yet.</body></html>")
    latest = recent_detections[0]
    img_b64 = latest.get("frame_b64")
    res = latest.get("result", {})
    return HTMLResponse(f"""
    <html><head><title>Debug</title></head><body>
    <h1>Latest Detection</h1>
    <p>Timestamp: {datetime.fromtimestamp(latest.get('timestamp', 0))}</p>
    <pre>{res}</pre>
    <img src="data:image/jpeg;base64,{img_b64}" style="max-width: 80vw;"/>
    </body></html>
    """)

# ---------------------- Main ----------------------
if __name__ == "__main__":
    if HDMI_ENABLED:
        print("Starting HDMI capture loop in background thread...", flush=True)
        threading.Thread(target=hdmi_loop, daemon=True).start()
    else:
        print("HDMI capture is disabled.", flush=True)

    print("Starting FastAPI server...", flush=True)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
