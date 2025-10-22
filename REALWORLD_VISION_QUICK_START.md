# Real-World Vision Gateway - Quick Start

**GPU**: Tesla K80 #2 (GPU 3) | **Port**: 8089 | **Status**: ✅ Ready for Testing

---

## Quick Deploy

```bash
# Build and start
docker compose build realworld-gateway
docker compose up -d realworld-gateway

# Watch logs
docker compose logs -f realworld-gateway

# Expected output:
# [webcam] Opened /dev/video0 @ 1920x1080 10fps
# [k80_realworld] Initializing on cuda:3...
# [k80_realworld] YOLOv8n loaded on cuda:3
# [k80_realworld] RetinaFace loaded
# [k80_realworld] MediaPipe Pose loaded
# [k80_realworld] Initialization complete!
```

---

## Test Endpoints

```bash
# Health check
curl http://localhost:8089/healthz

# Latest frame (JPEG)
curl http://localhost:8089/stream/latest.jpg -o webcam.jpg
xdg-open webcam.jpg

# Recent detections (JSON)
curl http://localhost:8089/api/detections | jq

# Debug UI (browser)
xdg-open http://localhost:8089/debug

# MJPEG stream (test in VLC)
vlc http://localhost:8089/stream/mjpeg
```

---

## Home Assistant Integration

**1. Add Camera Config**:
```bash
# Copy camera config to HA
cp ha_config/glados_vision_cameras.yaml /path/to/homeassistant/config/

# Edit configuration.yaml
# Add this line:
camera: !include glados_vision_cameras.yaml
```

**2. Restart Home Assistant**:
- Settings → System → Restart

**3. Add Camera Cards**:
- Overview → Edit Dashboard → Add Card → Camera
- Select: `camera.glados_webcam_vision`
- Select: `camera.glados_screen_vision`

**4. Listen for Events**:
- Developer Tools → Events → Listen to Event
- Event type: `vision.realworld_scene_change`
- Walk in front of webcam to trigger!

---

## What It Does

**Continuous Detection** (5-10 FPS on K80):
- ✅ **People**: YOLOv8n person detection
- ✅ **Faces**: RetinaFace face detection
- ✅ **Pose**: MediaPipe pose estimation (standing/sitting)
- ✅ **Gestures**: Simple wave detection

**Smart Triggering** (only when scene changes):
- ✅ **Qwen Analysis**: Deep scene understanding (~10x reduction vs continuous)
- ✅ **Face Recognition**: CompreFace identification
- ✅ **HA Events**: Send to Home Assistant
- ✅ **Memory Storage**: Store in Letta (optional)

**Video Streaming**:
- ✅ **MJPEG Stream**: `http://realworld-gateway:8089/stream/mjpeg`
- ✅ **Static Frame**: `http://realworld-gateway:8089/stream/latest.jpg`

---

## Verify It Works

### Step 1: Check GPU Access
```bash
docker exec -it realworld-gateway nvidia-smi
```
**Expected**: Shows Tesla K80, GPU 3, 24GB VRAM

### Step 2: Check Webcam Capture
```bash
docker compose logs realworld-gateway | grep "Opened"
```
**Expected**: `[webcam] Opened /dev/video0 @ 1920x1080 10fps`

### Step 3: Check Model Loading
```bash
docker compose logs realworld-gateway | grep "loaded"
```
**Expected**:
- `[k80_realworld] YOLOv8n loaded on cuda:3`
- `[k80_realworld] RetinaFace loaded`
- `[k80_realworld] MediaPipe Pose loaded`

### Step 4: Trigger Detection
```bash
# Stand in front of webcam
# Wait 2-3 seconds
docker compose logs realworld-gateway | grep "Scene change"
```
**Expected**: `[webcam] Scene change detected, triggering Qwen analysis...`

### Step 5: Check HA Dashboard
- Open Home Assistant
- Go to camera entities
- Should see live webcam feed with detections!

---

## Troubleshooting

### Service won't start
```bash
# Check GPU visibility
docker exec -it realworld-gateway nvidia-smi

# Rebuild if needed
docker compose build --no-cache realworld-gateway
docker compose up -d realworld-gateway
```

### Webcam not accessible
```bash
# Check on host
ls -la /dev/video0

# Check in container
docker exec -it realworld-gateway ls -la /dev/video0

# If missing, verify docker-compose.yml:
# devices:
#   - /dev/video0:/dev/video0
```

### Models not loading
```bash
# Check internet access (models auto-download)
docker exec -it realworld-gateway ping -c 3 google.com

# Check disk space (models ~10MB total)
df -h

# Manually trigger download (inside container)
docker exec -it realworld-gateway python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### No detections
```bash
# Verify you're in front of webcam
# Check processing interval
docker compose logs realworld-gateway | grep "Process"

# Should process every 3rd frame
# If no output, check PROCESS_EVERY_N env var
```

### MJPEG stream not working
```bash
# Test stream endpoint
curl -I http://localhost:8089/stream/mjpeg

# Expected: HTTP/1.1 200 OK

# If 404, check logs for errors
docker compose logs realworld-gateway | grep -i "error\|exception"
```

---

## Configuration

**Environment Variables** (in `docker-compose.yml`):

```yaml
# GPU settings
- K80_ENABLED=true              # Enable K80 preprocessing
- K80_DEVICE=cuda:3             # GPU 3 (Tesla K80 #2)
- K80_SCENE_CHANGE_THRESHOLD=0.3  # Sensitivity (0.0-1.0)

# Webcam settings
- WEBCAM_DEVICE=/dev/video0     # Webcam device
- WEBCAM_WIDTH=1920             # Resolution width
- WEBCAM_HEIGHT=1080            # Resolution height
- WEBCAM_FPS=10                 # Capture FPS

# Processing
- PROCESS_EVERY_N=3             # Process every Nth frame (1=all frames)

# Optional: CompreFace
- COMPREFACE_URL=http://compreface-api:8000
- COMPREFACE_API_KEY=your_key_here
```

---

## Performance Tuning

**Faster Detection** (more GPU usage):
```yaml
- PROCESS_EVERY_N=1  # Process every frame (10 FPS)
```

**Slower Detection** (less GPU usage):
```yaml
- PROCESS_EVERY_N=5  # Process every 5th frame (2 FPS)
```

**More Sensitive Scene Changes** (more Qwen calls):
```yaml
- K80_SCENE_CHANGE_THRESHOLD=0.5  # Trigger more often
```

**Less Sensitive Scene Changes** (fewer Qwen calls):
```yaml
- K80_SCENE_CHANGE_THRESHOLD=0.2  # Trigger less often
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Webcam (/dev/video0)                     │
│                        1920x1080 @ 10 FPS                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              K80 GPU 3 Lightweight Detection                │
│  ┌───────────┬──────────────┬───────────────┬─────────────┐ │
│  │ YOLOv8n   │ RetinaFace   │ MediaPipe     │ Gesture     │ │
│  │ (People)  │ (Faces)      │ (Pose)        │ Recognition │ │
│  │ ~6MB      │ ~1MB         │ ~3MB          │ Heuristics  │ │
│  └───────────┴──────────────┴───────────────┴─────────────┘ │
│                 Scene Change Tracker                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                    Scene Changed?
                          │
                          ▼ YES
┌─────────────────────────────────────────────────────────────┐
│         GPU 0 (1080 Ti) - Qwen2.5-VL Deep Analysis          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ • Who is here? (CompreFace face recognition)         │   │
│  │ • What are they doing? (activity classification)     │   │
│  │ • Engagement level? (focused/distracted/away)        │   │
│  │ • Overall scene context                              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Home Assistant Event Bus                       │
│  Event: vision.realworld_scene_change                       │
│  {                                                           │
│    "people_count": 2,                                        │
│    "face_identifications": [...],                            │
│    "gestures": ["wave_left"],                                │
│    "vl": {activity, engagement, reasoning}                   │
│  }                                                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│           Letta Memory System (Optional)                    │
│  Store: Presence, Activity, Context for recall              │
└─────────────────────────────────────────────────────────────┘
```

---

## What's Next?

1. ✅ **Test basic functionality** (follow Quick Deploy above)
2. ✅ **Add HA camera integration** (follow HA Integration section)
3. ✅ **Test scene change triggers** (walk in/out of frame)
4. ⏳ **Configure CompreFace** (optional, for face recognition)
5. ⏳ **Integrate with Letta memory** (optional, for context storage)
6. ⏳ **Create voice queries** ("Hey GLaDOS, who's here?")

---

## Key Files

- **Main App**: `services/realworld-gateway/app/main.py`
- **K80 Processor**: `services/realworld-gateway/app/k80_realworld_processor.py`
- **Docker Config**: `docker-compose.yml` (search for `realworld-gateway`)
- **HA Camera Config**: `ha_config/glados_vision_cameras.yaml`
- **Full Documentation**: `docs/implementation/GPU3_REALWORLD_VISION_COMPLETE.md`

---

## Support

**Logs**: `docker compose logs -f realworld-gateway`
**Health**: `curl http://localhost:8089/healthz`
**Debug**: `http://localhost:8089/debug`

**Need Help?** Check `docs/implementation/GPU3_REALWORLD_VISION_COMPLETE.md` for detailed troubleshooting.

---

**Status**: ✅ Ready to test! Build it, start it, and wave at your webcam! 👋
