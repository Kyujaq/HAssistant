# vision-router (K80 VM)

This service ingests Frigate or screen-capture events on the K80 box, scores their usefulness, and escalates high-value frames to the orchestrator for Qwen-VL summarisation. It now exposes:

- `POST /events` – unified events with OCR/detection metadata (honours `vision_on` + `screen_watch_on` runtime flags).
- `GET/POST /config` – runtime switches/overrides (`vision_on`, `screen_watch_on`, `threshold`, `max_frames`), mirrored to Prometheus gauge `vision_config_state{key=*}`.
- `GET /stats` – queue depth, lock state, totals, and NVML GPU telemetry (`gpus[index].util` / `mem_free_gb`).
- `GET/POST /lock` – manual lock (kept for HA ops/debugging).
- `GET /metrics` – Prometheus counters/gauges (events, esc totals, GPU gauges, skipped counts).
- `GET /health` – readiness probe.

Environment variables:

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

### Smoke test

```bash
curl -X POST http://vision-router:8050/events \
  -H 'Content-Type: application/json' \
  -d '{"source":"screen","ts":1730000000,"frames":[{"url":"http://example/frames/slide.jpg","width":1920,"height":1080,"ocr":{"text":"Slide 3: Agenda","conf":0.91}}],"tags":["meeting"]}'
```

Expected response: `{"id":"...","score":0.xx,"escalated":true}` and two calls to the orchestrator (`/vision/event` before/after VL enrichment).
