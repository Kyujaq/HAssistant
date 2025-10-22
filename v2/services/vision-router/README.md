# vision-router (K80 VM)

This service ingests Frigate or screen-capture events on the K80 box, scores their usefulness, and escalates high-value frames to the orchestrator for Qwen-VL summarisation.

## Endpoints

- `POST /events` – unified events with OCR/detection metadata (honors `vision_on`, `screen_watch_on`, and `escalate_vl` runtime flags).
- `POST /analyze` – ad-hoc analysis for HA with explicit frames/URLs. Bypasses vision_on/screen_watch_on and always escalates to VL (if `escalate_vl` enabled). Returns full VL result + bundle.
- `GET/POST /config` – runtime switches/overrides:
  - `vision_on` (bool) – master switch for vision processing
  - `screen_watch_on` (bool) – enable/disable screen-capture events
  - `escalate_vl` (bool) – enable/disable VL escalation (added for B1)
  - `threshold` (float) – usefulness threshold for escalation (0.0-1.0)
  - `max_frames` (int) – top-K frames to forward to VL
  - All config changes mirrored to Prometheus gauge `vision_config_state{key=*}`.
- `GET /stats` – queue depth, lock state, totals, config, and cached NVML GPU telemetry (`gpus[index].util` / `mem_free_gb`).
- `GET/POST /lock` – manual lock (kept for HA ops/debugging).
- `GET /metrics` – Prometheus counters/gauges:
  - `vision_events_total{source}` – total events by source
  - `vision_escalations_total{reason}` – escalations (useful/adhoc)
  - `vision_events_skipped_total{reason}` – skipped events
  - `vision_vl_failovers_total` – VL escalation failures
  - `vision_analyze_requests_total{source}` – ad-hoc analyze requests
  - `vision_gpu_util_percent{index}` – GPU utilization %
  - `vision_gpu_mem_free_gb{index}` – GPU free memory (GB)
  - `vision_pending_jobs` – current queue depth
  - `vision_lock` – lock state (0/1)
- `GET /health` – readiness probe.

## Features

### NVML Background Poller (B2)
- Polls GPU stats every 5 seconds in background task
- Maintains 60s utilization history (12 samples) for backpressure detection
- `/stats` endpoint returns cached data (refreshed max every 3s) for fast responses
- Updates Prometheus gauges: `vision_gpu_util_percent{index}`, `vision_gpu_mem_free_gb{index}`

### Backpressure & Auto-Threshold Adjustment (B3)
- Checks every escalation if queue depth > 5 OR avg GPU util > 85% for 60s
- Auto-raises threshold by +0.1 (capped at 0.85) to reduce load
- Only adjusts once per 30s to avoid oscillation
- Logs warnings with backpressure metrics

### Error Handling
- VL escalation failures tracked in `vision_vl_failovers_total` counter
- Orchestrator push failures logged but don't block event processing
- GPU poller errors caught and logged without crashing service
- All timeouts explicitly set (orchestrator: 8s, VL: 60s, lock sync: 4s)

## Environment Variables

- `ORCHESTRATOR_URL` – main orchestrator host (default `http://orchestrator:8020`)
- `VL_GATEWAY_URL` – endpoint to invoke Qwen-VL (default `http://orchestrator:8020`)
- `VISION_ESCALATE_VL` – enable escalations (`1` by default)
- `VISION_ESCALATE_THRESHOLD` – usefulness threshold (`0.55` default)
- `VISION_MAX_FRAMES` – top-K frames to forward (`3` default)
- `VISION_LOCK_ON_ESCALATE` – toggle orchestrator lock while escalating (`1` default)

Build and run on the VM with the provided compose snippet or:

```bash
docker build -t vision-router v2/services/vision-router
docker run --rm -p 8050:8050 \
  -e ORCHESTRATOR_URL=http://<main-host>:8020 \
  -e VL_GATEWAY_URL=http://<main-host>:8020 \
  vision-router
```

### Home Assistant wiring

- Switches: `switch.vision_on` / `switch.screen_watch_on` POST to `http://vision-router:8050/config` with `{ "vision_on": true }`, `{ "screen_watch_on": false }`, etc.
- Sensors: `sensor.vision_router_queue_depth` hits `http://vision-router:8050/stats` and surfaces queue, lock, totals, and GPU info. Template sensors read the attributes for dashboards/alerts.
- Prometheus: `/metrics` already exposes counters/gauges for graphs.

## Smoke Tests

### Test /events endpoint
```bash
curl -X POST http://vision-router:8050/events \
  -H 'Content-Type: application/json' \
  -d '{"source":"screen","ts":1730000000,"frames":[{"url":"http://example/frames/slide.jpg","width":1920,"height":1080,"ocr":{"text":"Slide 3: Agenda","conf":0.91}}],"tags":["meeting"]}'
```

Expected response: `{"id":"...","score":0.xx,"escalated":true}` and two calls to the orchestrator (`/vision/event` before/after VL enrichment).

### Test /analyze endpoint (ad-hoc HA analysis)
```bash
curl -X POST http://vision-router:8050/analyze \
  -H 'Content-Type: application/json' \
  -d '{"source":"ha_manual","frames":[{"url":"http://192.168.2.13:8123/local/snapshot.jpg","ocr":{"text":"Dashboard view"}}],"tags":["dashboard"]}'
```

Expected response: `{"id":"...","source":"ha_manual","escalated":true,"vl":{...},"bundle":{...}}`

### Test /config runtime switches
```bash
# Disable VL escalation
curl -X POST http://vision-router:8050/config \
  -H 'Content-Type: application/json' \
  -d '{"escalate_vl":false}'

# Raise threshold to reduce escalations
curl -X POST http://vision-router:8050/config \
  -H 'Content-Type: application/json' \
  -d '{"threshold":0.75}'

# Check current config
curl http://vision-router:8050/config
```

### Test /stats (with GPU telemetry)
```bash
curl http://vision-router:8050/stats
```

Expected response includes `queue_depth`, `lock_enabled`, `events_total`, `escalations_total`, `config`, and `gpus` array with K80 stats.

The orchestrator exposes `/vision/config` as a pass-through so Home Assistant can post toggles to one place; the router still honours `/config` and `/stats` directly when needed.
