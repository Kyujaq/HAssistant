# realworld-gateway (K80 VM)

Processes camera feeds (people/pose/motion heuristics) on the K80 host and relays normalised events to vision-router.

## Endpoints
- POST /frame – ingest a frame via multipart upload, image_url, or image_b64 (optional JSON detections, meta).
- GET /frames/{id}.jpg / /frames/latest.jpg – fetch cached frames.
- GET /mjpeg/cam – MJPEG stream suitable for Home Assistant.
- GET /stats – FPS, totals, GPU telemetry.
- GET /metrics – Prometheus exposition.
- GET /health – readiness.

## Environment
- VISION_ROUTER_URL (default http://vision-router:8050).
- PUBLIC_URL (default http://localhost:8052).

## Run locally
`ash
docker build -t realworld-gateway ../services --file realworld-gateway/Dockerfile
docker run --rm -p 8052:8052 \
  -e VISION_ROUTER_URL=http://vision-router:8050 \
  -e PUBLIC_URL=http://realworld-gateway:8052 \
  realworld-gateway
`

The current implementation uses lightweight motion heuristics as a placeholder; drop in your detector pose/face models and populate the detections list before forwarding to the router.
