# Frigate + realworld-gateway Integration Plan

**Date**: 2025-10-12
**Goal**: Combine Frigate's strengths with custom intelligence layer

---

## Current Situation

### Frigate
- **Status**: Running but **not configured** (dummy camera config)
- **GPU**: GPU 1 (GTX 1070)
- **Capabilities**: Person detection (TensorFlow Lite), recording, motion, zones
- **What it's missing**: Face recognition, pose, gestures, scene understanding

### realworld-gateway
- **Status**: ✅ Working (just tested)
- **GPU**: GPU 3 (Tesla K80 #2)
- **Capabilities**: YOLOv8n, MediaPipe pose, gestures, CompreFace, Qwen
- **What it's missing**: Recording, motion zones, mature detection pipeline

---

## Problem: Overlap

Both services want to:
- Access `/dev/video0` (webcam)
- Detect people
- Use GPU resources

---

## Solution: 3 Options

### Option 1: **Parallel Operation** (Current State)
- Both access webcam independently
- Frigate: Basic detection + recording
- realworld-gateway: Intelligence layer

**Pros**:
- No code changes needed
- Works today

**Cons**:
- Duplicate detection work
- Both accessing webcam (may conflict)
- GPU usage on both GPUs

---

### Option 2: **Frigate → realworld-gateway Pipeline** (RECOMMENDED ⭐)

**Architecture**:
```
Webcam → Frigate (GPU 1) → MQTT/HTTP → realworld-gateway (GPU 3) → HA
         │                               │
         • Person detection              • Face recognition
         • Motion zones                  • Pose estimation
         • Recording                     • Gestures
         • Clips                         • Qwen scene understanding
```

**Implementation**:
1. **Frigate**: Configure for webcam, enable person detection
2. **realworld-gateway**: Modify to consume Frigate snapshots instead of direct webcam
3. **Communication**: HTTP API or MQTT

**Pros**:
- No duplicate detection
- Frigate does what it's best at
- Custom adds intelligence layer
- Clear separation of concerns

**Cons**:
- Requires code changes to realworld-gateway
- Slight latency (Frigate → custom)

---

### Option 3: **Use Only Frigate** (Simplest)

Disable `realworld-gateway`, use only Frigate

**Pros**:
- Simpler architecture
- Mature, battle-tested

**Cons**:
- ❌ Lose face recognition
- ❌ Lose pose estimation
- ❌ Lose gesture detection
- ❌ Lose Qwen scene understanding

**Verdict**: **Not recommended** - loses too much value

---

## Recommended Implementation: Option 2

### Phase 1: Configure Frigate for Webcam

**File**: `frigate/config/config.yaml`

```yaml
mqtt:
  enabled: true  # Enable for inter-service communication
  host: <mqtt-broker>  # Add MQTT broker if available

cameras:
  webcam:
    enabled: true
    ffmpeg:
      inputs:
        - path: /dev/video0
          input_args: preset-v4l2
          roles:
            - detect
            - record
    detect:
      enabled: true
      width: 1920
      height: 1080
      fps: 5

    objects:
      track:
        - person
      filters:
        person:
          min_area: 5000
          threshold: 0.7

    snapshots:
      enabled: true
      timestamp: true
      bounding_box: true

    record:
      enabled: true
      retain:
        days: 2
        mode: motion

detect:
  enabled: true
  width: 1920
  height: 1080
  fps: 5

detectors:
  cpu:
    type: cpu  # Or tensorrt for GPU
```

### Phase 2: Modify realworld-gateway to Consume Frigate

**Changes to `services/realworld-gateway/app/main.py`**:

```python
# New mode: FRIGATE_MODE
FRIGATE_MODE = os.getenv("FRIGATE_MODE", "false").lower() == "true"
FRIGATE_URL = os.getenv("FRIGATE_URL", "http://frigate:5000")

if FRIGATE_MODE:
    # Subscribe to Frigate events via HTTP polling or MQTT
    # When person detected:
    #   1. Fetch snapshot from Frigate API
    #   2. Run face recognition (CompreFace)
    #   3. Run pose estimation (MediaPipe)
    #   4. Run gesture detection
    #   5. Trigger Qwen on scene change
    #   6. Send enriched event to HA
else:
    # Current mode: direct webcam access
    pass
```

**Frigate API for Snapshots**:
```python
# Fetch latest snapshot
response = requests.get(f"{FRIGATE_URL}/api/webcam/latest.jpg")
img = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)

# OR subscribe to MQTT events
# Topic: frigate/events
# Payload: {"type": "new", "after": {"label": "person", ...}}
```

### Phase 3: Docker Compose Integration

**Update `docker-compose.yml`**:

```yaml
realworld-gateway:
  environment:
    - FRIGATE_MODE=true  # Enable Frigate integration
    - FRIGATE_URL=http://frigate:5000
    - WEBCAM_ENABLED=false  # Disable direct webcam access
  depends_on:
    - frigate
```

**Update Frigate**:
```yaml
frigate:
  devices:
    - /dev/video0:/dev/video0  # Give Frigate exclusive webcam access
```

---

## Phase-by-Phase Implementation

### Phase 1: Fix Frigate Config (30 min)
1. Update `frigate/config/config.yaml` with webcam config
2. Restart Frigate: `docker compose restart frigate`
3. Verify in Frigate UI: `http://localhost:5000`
4. Check person detection works

### Phase 2: Add Frigate API Client (1 hour)
1. Create `services/realworld-gateway/app/frigate_client.py`
2. Add HTTP polling for Frigate events
3. Add snapshot fetching
4. Test without disabling direct webcam yet

### Phase 3: Modify Main App (1 hour)
1. Update `main.py` to support `FRIGATE_MODE`
2. When enabled, poll Frigate instead of webcam
3. Keep all intelligence layer (face, pose, gestures, Qwen)

### Phase 4: Testing (30 min)
1. Enable `FRIGATE_MODE=true`
2. Disable `WEBCAM_ENABLED=false`
3. Test person detection → face recognition → pose → gestures
4. Verify no conflicts

### Phase 5: Optimize (30 min)
1. Add MQTT subscription (faster than polling)
2. Cache Frigate snapshots
3. Reduce latency

**Total Time**: ~3.5 hours

---

## Alternative: Keep Both Running in Parallel

**If you don't want to change anything**:

### Divide Responsibilities

**Frigate**:
- Motion detection & zones
- 24/7 recording
- Basic person detection
- Clips & notifications

**realworld-gateway**:
- Face recognition (CompreFace)
- Pose estimation (standing/sitting)
- Gesture recognition
- Qwen scene understanding
- Smart scene change tracking

**How they coexist**:
- Both access `/dev/video0` (Docker allows shared device access)
- Frigate: Records & detects continuously
- realworld-gateway: Adds intelligence layer
- Home Assistant: Receives events from both

**Benefits**:
- ✅ Works today (no code changes)
- ✅ Get Frigate's mature features
- ✅ Keep custom intelligence layer

**Drawbacks**:
- ⚠️ Both services doing person detection (duplicate work)
- ⚠️ Higher GPU/CPU usage
- ⚠️ Potential webcam access conflicts (unlikely but possible)

---

## My Recommendation

### Short-term (Today): **Keep Both Parallel**
- Configure Frigate for webcam (see config above)
- Keep realworld-gateway as-is
- Benefit from both immediately
- Monitor for conflicts

### Medium-term (Next Week): **Integrate via Frigate API**
- Modify realworld-gateway to consume Frigate snapshots
- Disable direct webcam access in realworld-gateway
- Give Frigate exclusive webcam control
- Add intelligence layer on top

---

## Feature Comparison Table

| Feature | Frigate Only | realworld Only | Both Parallel | Frigate→realworld |
|---------|--------------|----------------|---------------|-------------------|
| Person Detection | ✅ Basic | ✅ YOLOv8n | ✅✅ Both | ✅ Frigate only |
| Face Recognition | ❌ | ✅ | ✅ | ✅ |
| Pose Estimation | ❌ | ✅ | ✅ | ✅ |
| Gestures | ❌ | ✅ | ✅ | ✅ |
| Qwen Scene AI | ❌ | ✅ | ✅ | ✅ |
| Recording/Clips | ✅ | ❌ | ✅ | ✅ |
| Motion Zones | ✅ | ❌ | ✅ | ✅ |
| Mature UI | ✅ | ❌ | ✅ | ✅ |
| **Duplicate Work** | No | No | ⚠️ **Yes** | **No** |
| **GPU Efficiency** | High | High | ⚠️ **Lower** | **High** |

**Winner**: **Frigate→realworld** (Option 2) for long-term, **Both Parallel** for immediate use

---

## Implementation Steps (Quick Start)

### Today: Enable Both Parallel

1. **Fix Frigate Config**:
```bash
sudo nano frigate/config/config.yaml
# Update camera config as shown above
```

2. **Restart Frigate**:
```bash
docker compose restart frigate
```

3. **Keep realworld-gateway running**:
```bash
# Already running and working!
```

4. **Test**:
```bash
# Check Frigate: http://localhost:5000
# Check realworld: http://localhost:8089/debug
```

### Next Week: Integrate

1. **Create Frigate Client**:
```bash
# Add frigate_client.py to realworld-gateway
```

2. **Update docker-compose.yml**:
```yaml
realworld-gateway:
  environment:
    - FRIGATE_MODE=true
    - WEBCAM_ENABLED=false
```

3. **Test Integration**:
```bash
docker compose restart realworld-gateway
docker compose logs -f realworld-gateway
```

---

## Conclusion

**Answer**: Yes, integrate them! Use Frigate for what it does best (detection, recording, zones), and add your custom intelligence layer (face, pose, gestures, Qwen) on top.

**Today**: Keep both running in parallel (works fine, minor inefficiency)
**This Week**: Integrate via Frigate API (best long-term solution)

Your instinct was right - we can leverage Frigate! 🎯
