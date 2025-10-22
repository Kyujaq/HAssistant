# vision-gateway (K80 VM)

Lightweight FastAPI service that captures screen/UI frames on the K80 GPU box, applies an OCR/UI heuristic, and posts normalised events to the vision-router.

## Endpoints
- POST /frame – ingest a frame (multipart upload, image_url, or base64). Accepts optional 	ags, meta, and OCR hints.
- GET /frames/{id}.jpg / /frames/latest.jpg – serve cached frames.
- GET /mjpeg/screen – MJPEG stream for HA camera cards.
- GET /stats – FPS, totals, GPU telemetry.
- GET /metrics – Prometheus metrics.
- GET /health – readiness.

## Environment
- VISION_ROUTER_URL (default http://vision-router:8050)
- ORCHESTRATOR_URL (optional) – reserved for future direct memory writes.
- PUBLIC_URL – base URL used when emitting frame links (defaults to http://localhost:8051).

## Run locally
`ash
docker build -t vision-gateway ../services --file vision-gateway/Dockerfile
docker run --rm -p 8051:8051 \
  -e VISION_ROUTER_URL=http://vision-router:8050 \
  -e PUBLIC_URL=http://vision-gateway:8051 \
  vision-gateway
`

Use the /frame endpoint to send sample images; the service forwards valid events to the router once schema validation passes.
