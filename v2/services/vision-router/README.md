# vision-router (K80 VM)

This service ingests Frigate or screen-capture events on the K80 box, scores their usefulness, and escalates high-value frames to the orchestrator for Qwen-VL summarisation. It exposes:

- `/events` – POST unified events with OCR/detection metadata
- `/lock` – GET/POST for toggling the vision lock
- `/metrics` – Prometheus counters and gauges
- `/health` – readiness probe

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
  vision-router
```
