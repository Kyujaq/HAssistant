# K80 Vision Upgrade Roadmap

## Overview
This document outlines the plan to integrate the Tesla K80 GPU into vision-gateway for GPU-accelerated preprocessing, enabling advanced vision capabilities for voice-controlled screen interaction.

---

## Current State (CPU-Only)

### Vision Gateway Limitations
- **Template matching only** - Fixed button detection using OpenCV on CPU
- **Single-shot Qwen calls** - Heavy VL model called every time button pressed
- **Limited preprocessing** - Just resize and grayscale conversion
- **Specific use case** - Meeting invite detection only
- **Had to scrap features** - Advanced vision features cut due to CPU constraints

### Current Flow
```
HDMI Capture (1920x1080 @ 10fps)
    ↓
Template Matching (CPU - OpenCV) → Detect "Send" button
    ↓
Button Pressed? → Capture full-res screenshot
    ↓
Call Qwen2.5-VL (GPU 0 - GTX 1080 Ti) → Analyze entire frame
    ↓
Event to HA + Context extraction
```

**Problems:**
- ❌ Can only detect pre-defined buttons
- ❌ Qwen called on every press (slow, expensive)
- ❌ No general-purpose UI element detection
- ❌ Can't track scene changes continuously

---

## Target State (With K80)

### K80 Capabilities (24GB VRAM)
- **Dual GPU** - 2x 12GB (more than enough for preprocessing)
- **Continuous processing** - Run detection at 5-10 FPS
- **Smart triggering** - Only call heavy Qwen when needed
- **General purpose** - Detect any UI element, not just buttons

### New GPU Allocation
```
GPU 0 (GTX 1080 Ti - 11GB):  Qwen2.5-VL (vision analysis, 7B model)
GPU 1 (GTX 1070):            Hermes-3 + Whisper + Piper + Frigate
GPU 2 (Tesla K80 - 24GB):    Vision preprocessing + object detection
```

### Enhanced Flow
```
HDMI Capture (1920x1080 @ 10fps)
    ↓
K80: Continuous Object Detection (YOLOv8/GroundingDINO @ 5-10 FPS)
    ↓
K80: Scene Understanding
    • Detect all UI elements (buttons, text fields, dialogs)
    • Track changes (new windows, popups, state changes)
    • Extract bounding boxes and labels
    ↓
K80: Smart Decision
    • Is this interesting? (New element? Scene change?)
    • Yes → Call Qwen2.5-VL for deep analysis
    • No → Continue monitoring
    ↓
GPU 0 (GTX 1080 Ti): Qwen2.5-VL (only when needed)
    • Deep semantic understanding
    • Context extraction
    • Action recommendation
    ↓
AI Task Result → HA → Computer Control Agent
```

**Benefits:**
- ✅ Detect ANY UI element (buttons, links, text boxes, etc.)
- ✅ Continuous scene monitoring (not event-based)
- ✅ Smart Qwen triggering (10x fewer heavy calls)
- ✅ General-purpose vision (not meeting-specific)
- ✅ Can re-enable scrapped features

---

## Implementation Phases

### Phase 1: Hardware & Docker Setup
**Goal:** Get K80 recognized and allocated to vision-gateway

**Tasks:**
1. ✅ Plug in K80 (waiting for adapter)
2. Verify recognition: `nvidia-smi` should show 3 GPUs
3. Update `docker-compose.yml`:
   ```yaml
   vision-gateway:
     deploy:
       resources:
         reservations:
           devices:
             - capabilities: [gpu]
               device_ids: ['2']  # K80
   ```
4. Update vision-gateway Dockerfile to include CUDA support
5. Test GPU access: `docker exec vision-gateway nvidia-smi`

**Deliverable:** vision-gateway has access to K80

---

### Phase 2: Add Object Detection Model
**Goal:** Run continuous object detection on K80

**Model Selection (choose one):**

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| **YOLOv8n** | 6MB | 80+ FPS | Good | Fast general detection |
| **YOLOv8s** | 22MB | 60+ FPS | Better | Balanced speed/accuracy |
| **GroundingDINO** | 694MB | 10-20 FPS | Excellent | Text-prompted detection ("find accept button") |
| **OWLv2** | ~1GB | 5-10 FPS | Excellent | Open-vocabulary detection |

**Recommendation:** Start with **GroundingDINO**
- Text-prompted: Can detect "accept button", "send button", etc. without training
- Fast enough: 10-20 FPS on K80 is plenty for UI monitoring
- General purpose: Works for any UI element

**Tasks:**
1. Install dependencies:
   ```dockerfile
   # vision-gateway/Dockerfile
   RUN pip install torch torchvision \
       transformers \
       groundingdino-py
   ```

2. Create preprocessing module:
   ```python
   # vision-gateway/app/k80_preprocessor.py

   from groundingdino.util.inference import Model

   class K80Preprocessor:
       def __init__(self, device='cuda:2'):  # K80
           self.model = Model(
               model_config_path="...",
               model_checkpoint_path="...",
               device=device
           )

       def detect_elements(self, frame, prompts=["button", "dialog", "window"]):
           """Continuous detection at 5-10 FPS"""
           detections = self.model.predict_with_caption(
               image=frame,
               caption=" . ".join(prompts),
               box_threshold=0.35,
               text_threshold=0.25
           )
           return detections  # boxes, labels, scores
   ```

3. Integrate into main loop:
   ```python
   # Replace template matching with K80 detection
   preprocessor = K80Preprocessor(device='cuda:2')

   while True:
       ok, frame = cap.read()

       # K80: Continuous detection
       elements = preprocessor.detect_elements(
           frame,
           prompts=["button", "send button", "accept button", "dialog box"]
       )

       # Track scene changes
       if scene_changed(elements):
           # Call Qwen for deep analysis
           qwen_result = call_qwen_vl(frame)
   ```

**Deliverable:** vision-gateway runs continuous object detection on K80

---

### Phase 3: Smart Qwen Triggering
**Goal:** Only call heavy Qwen model when scene changes significantly

**Scene Change Detection:**
```python
class SceneTracker:
    def __init__(self, threshold=0.3):
        self.last_elements = []
        self.threshold = threshold

    def has_changed(self, new_elements):
        """Compare current elements to last frame"""
        if not self.last_elements:
            return True  # First frame

        # Calculate IoU overlap, label similarity, etc.
        similarity = compute_similarity(self.last_elements, new_elements)

        changed = similarity < (1.0 - self.threshold)
        if changed:
            self.last_elements = new_elements
        return changed
```

**Smart Triggering Logic:**
```python
scene_tracker = SceneTracker(threshold=0.3)

while True:
    # K80: Always detect
    elements = preprocessor.detect_elements(frame)

    # Only call Qwen on significant changes
    if scene_tracker.has_changed(elements):
        logger.info(f"Scene changed, calling Qwen: {elements}")
        qwen_result = call_qwen_vl(frame)

        # Send to HA AI Task
        ai_task_result = {
            "detected_elements": elements,
            "semantic_analysis": qwen_result,
            "timestamp": time.time()
        }
```

**Deliverable:** 10x reduction in Qwen calls, faster response

---

### Phase 4: Update AI Task Integration
**Goal:** Expose enhanced vision capabilities to Home Assistant

**Update `ai_task.py`:**
```python
async def _async_generate_data(
    self, task: GenDataTask, chat_log: Any
) -> GenDataTaskResult:
    """Enhanced with K80 preprocessing."""

    # Get latest detections from vision-gateway
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{VISION_GATEWAY_URL}/api/detections/latest"
        ) as response:
            detection_data = await response.json()

    # Parse user intent from instructions
    intent = parse_intent(task.instructions)

    if intent == "click":
        # Find clickable element matching description
        target = find_element(detection_data, task.instructions)
        return GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data={
                "action": "click",
                "element": target["label"],
                "coordinates": target["bbox"],
                "confidence": target["score"]
            }
        )

    elif intent == "analyze":
        # Return all detected elements
        return GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data={
                "elements": detection_data["elements"],
                "semantic_analysis": detection_data.get("qwen_result"),
                "scene_description": generate_description(detection_data)
            }
        )
```

**New Vision Gateway Endpoints:**
```python
@app.get("/api/detections/latest")
def get_latest_detections():
    """Return latest K80 detections + Qwen analysis if available"""
    return {
        "elements": current_detections,  # From K80
        "qwen_result": last_qwen_result,  # From Qwen2.5-VL
        "timestamp": time.time()
    }

@app.post("/api/find_element")
def find_element(query: str):
    """Find specific element by text description"""
    # Use GroundingDINO to find element matching query
    return {
        "found": True,
        "label": "accept button",
        "bbox": [x, y, w, h],
        "confidence": 0.92
    }
```

**Deliverable:** AI Task can detect and locate any UI element

---

### Phase 5: Computer Control Integration
**Goal:** Complete voice-to-click pipeline

**Flow:**
```
Voice: "Click the accept button"
    ↓
HA Assist → Ollama (with AI Task tools)
    ↓
ai_task.generate_data(instructions="Find and click accept button")
    ↓
Vision Gateway:
    • K80: Detect all UI elements
    • Find "accept button"
    • Return coordinates
    ↓
Computer Control Agent:
    • Receive coordinates from AI Task
    • Execute click(x, y)
    ↓
Done! Button clicked
```

**Create HA Service for Clicking:**
```yaml
# configuration.yaml
rest_command:
  computer_control_click:
    url: "http://hassistant-computer-control:8089/click"
    method: POST
    headers:
      content-type: "application/json"
    payload: >
      {
        "x": {{ x }},
        "y": {{ y }}
      }
```

**Create Automation:**
```yaml
# automations.yaml
- alias: "Voice Click Button"
  trigger:
    - platform: conversation
      command: "Click the {element}"
  action:
    - service: ai_task.generate_data
      target:
        entity_id: ai_task.vision_control
      data:
        instructions: "Find {{ trigger.slots.element }}"
      response_variable: vision_result
    - service: rest_command.computer_control_click
      data:
        x: "{{ vision_result.data.coordinates[0] }}"
        y: "{{ vision_result.data.coordinates[1] }}"
```

**Deliverable:** Full voice-controlled screen interaction

---

## Performance Targets

### Current (CPU-Only)
- Template matching: ~50ms per frame
- Qwen calls: ~2-5 seconds
- Total latency: 2-5s per interaction
- Coverage: Pre-defined buttons only

### After K80 Upgrade
- K80 detection: ~100ms per frame (10 FPS)
- Qwen calls: ~2-5s (but 10x less frequent)
- Smart triggering: Scene change detection <10ms
- Total latency: ~200ms for simple clicks, 2-5s for complex analysis
- Coverage: Any UI element

---

## Testing Plan

### Phase 1: Hardware Test
```bash
# After K80 installed
nvidia-smi  # Should show GPU 2: Tesla K80
docker exec vision-gateway nvidia-smi  # Verify container access
```

### Phase 2: Detection Test
```python
# Test GroundingDINO detection
from k80_preprocessor import K80Preprocessor

preprocessor = K80Preprocessor()
test_frame = cv2.imread("test_screenshot.png")
detections = preprocessor.detect_elements(
    test_frame,
    prompts=["button", "accept button"]
)
print(detections)  # Should show detected buttons with bboxes
```

### Phase 3: Integration Test
```bash
# Call AI Task
curl -X POST http://localhost:8123/api/services/ai_task/generate_data \
  -H "Authorization: Bearer $HA_TOKEN" \
  -d '{
    "entity_id": "ai_task.vision_control",
    "instructions": "Find all buttons on screen"
  }'

# Should return list of detected buttons with coordinates
```

### Phase 4: End-to-End Test
Voice command: "Click the send button"
Expected: Computer control agent clicks the send button within 1 second

---

## Rollback Plan

If K80 integration has issues:

1. **Quick Rollback:**
   - Comment out K80 device in docker-compose.yml
   - Restart vision-gateway
   - Falls back to CPU template matching

2. **Partial Rollback:**
   - Keep K80 for preprocessing
   - Disable GroundingDINO
   - Use simpler YOLO model

3. **Code Rollback:**
   - Git branch: `feature/k80-integration`
   - Main branch keeps CPU-only implementation

---

## Future Enhancements (Post-K80)

### 1. OCR Integration
- Use K80 for text detection (EAST/CRAFT)
- Extract text from UI elements
- Voice: "Click the button that says X"

### 2. Multiple Monitor Support
- Track multiple HDMI inputs
- Route to correct screen
- Voice: "Click accept on monitor 2"

### 3. Action History
- Record all detected elements
- Build UI state graph
- Predict likely next actions

### 4. Smart Waiting
- Detect loading states
- Wait for elements to appear
- Voice: "Click accept when it appears"

### 5. Vision Memory
- Store UI layouts in Letta
- Learn application patterns
- Faster detection of known UIs

---

## Success Criteria

✅ **Phase 1 Complete:** K80 visible in `nvidia-smi` from vision-gateway container
✅ **Phase 2 Complete:** GroundingDINO detects UI elements at 5+ FPS
✅ **Phase 3 Complete:** Qwen calls reduced by 10x while maintaining accuracy
✅ **Phase 4 Complete:** AI Task returns element coordinates for any UI element
✅ **Phase 5 Complete:** Voice command "Click X" works end-to-end in <1 second

---

## Timeline Estimate

| Phase | Duration | Depends On |
|-------|----------|------------|
| Phase 1: Hardware Setup | 1-2 hours | K80 adapter arrives |
| Phase 2: Object Detection | 4-6 hours | Phase 1 |
| Phase 3: Smart Triggering | 2-3 hours | Phase 2 |
| Phase 4: AI Task Update | 2-3 hours | Phase 3 |
| Phase 5: Computer Control | 2-3 hours | Phase 4 |
| **Total** | **11-17 hours** | K80 adapter |

**Blockers:**
- ⏳ Waiting on K80 adapter (ordered)
- None otherwise - all other infrastructure ready

---

## Notes

- Current AI Task integration is **K80-ready** - interface won't change
- Vision-gateway refactor will be **backward compatible**
- Can test with CPU detection first (slower but functional)
- K80 upgrade is **purely additive** - no breaking changes to existing features

---

**Last Updated:** 2025-10-10
**Status:** Ready to implement when K80 adapter arrives
**Owner:** Vision Gateway Team
